from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_tesseract_msys2_license_evidence as evidence


class LicenseEvidenceTests(unittest.TestCase):
    def fixture(self, base: Path) -> tuple[Path, Path, Path, Path, Path, Path, dict]:
        root = base / "package"
        binary_dir = root / "mingw64/bin"
        license_dir = root / "mingw64/share/licenses/test"
        binary_dir.mkdir(parents=True)
        license_dir.mkdir(parents=True)
        (root / ".PKGINFO").write_text("license = spdx:Apache-2.0\n", encoding="utf-8")
        (license_dir / "LICENSE").write_text("fixture license text", encoding="utf-8")
        files = []
        for index in range(35):
            name = "tesseract.exe" if index == 0 else f"lib{index}.dll"
            binary = binary_dir / name
            binary.write_bytes(f"binary {index}".encode())
            files.append({"path": name, "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                          "package": "candidate", "version": "1", "archive_sha256": "abc"})
        manifest = base / "manifest.json"
        manifest.write_text(json.dumps({"release_eligible": False,
                                        "local_binary_count": 35, "files": files}), encoding="utf-8")
        graph = base / "graph.json"
        graph.write_text(json.dumps({"release_eligible": False, "unused_local_dlls": [],
                                     "non_root_dlls_not_in_static_graph": [],
                                     "needed_local_files": [item["path"] for item in files],
                                     "needed_sha256": {item["path"]: item["sha256"]
                                                       for item in files}}), encoding="utf-8")
        matrix, licenses, fallback = (base / name for name in
                                      ("matrix.csv", "licenses.csv", "fallback.csv"))
        for path, fields in ((matrix, ["dll", "official_sha256"]),
                             (licenses, ["dll"]), (fallback, ["dll"])):
            with path.open("w", encoding="utf-8", newline="") as output:
                csv.DictWriter(output, fieldnames=fields).writeheader()
        return manifest, graph, root, matrix, licenses, fallback, {
            ("candidate", "1"): {"root": root, "archive_sha256": "abc"}}

    def test_complete_non_release_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, graph, root, matrix, licenses, fallback, packages = self.fixture(Path(temp))
            with patch.object(evidence, "audit_inputs", return_value=packages):
                result = evidence.create_inventory(manifest, graph, root, matrix,
                                                   licenses, fallback)
            self.assertEqual(len(result), 35)
            self.assertTrue(all(row["evidence_status"] == "PACKAGE_TEXT_HASH_VERIFIED"
                                and row["release_obligations_reviewed"] == "NO" for row in result))

    def test_graph_mismatch_and_license_absence_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, graph, root, matrix, licenses, fallback, packages = self.fixture(Path(temp))
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_data["files"][0]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Manifest disagrees"):
                evidence.create_inventory(manifest, graph, root, matrix, licenses, fallback)
            manifest_data["files"][0]["sha256"] = hashlib.sha256(b"binary 0").hexdigest()
            manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
            (root / "mingw64/share/licenses/test/LICENSE").unlink()
            with patch.object(evidence, "audit_inputs", return_value=packages):
                with self.assertRaisesRegex(ValueError, "lacks license text"):
                    evidence.create_inventory(manifest, graph, root, matrix,
                                              licenses, fallback)


if __name__ == "__main__":
    unittest.main()
