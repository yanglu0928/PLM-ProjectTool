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
import build_tesseract_no_jbig_license_matrix as audit


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class NoJbigLicenseMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.csv = self.root / "prior.csv"
        self.graph = self.root / "graph.json"
        self.source = self.root / "source.tar.gz"
        self.license = self.root / "LICENSE.md"
        self.source.write_bytes(b"source")
        self.license.write_bytes(b"license")
        rows = []
        names = [f"lib{i:02d}.dll" for i in range(32)] + [audit.NEW_DLL, "tesseract.exe"]
        for name in names + [audit.REMOVED_DLL]:
            old_data = ("old:" + name).encode()
            actual_data = ("new:" + name).encode() if name == audit.NEW_DLL else old_data
            if name != audit.REMOVED_DLL:
                (self.candidate / name).write_bytes(actual_data)
            rows.append(dict(binary=name, binary_sha256=sha(old_data), package="package",
                             package_version="1", archive_sha256="a" * 64,
                             package_declared_license="spdx:MIT", evidence_status="PACKAGE_TEXT_HASH_VERIFIED",
                             evidence_paths="LICENSE", evidence_sha256="b" * 64))
        with self.csv.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        self.graph.write_text(json.dumps(dict(needed_local_files=names,
                                               needed_sha256={name: sha((self.candidate / name).read_bytes())
                                                              for name in names},
                                               unused_local_dlls=[], non_root_dlls_not_in_static_graph=[])),
                              encoding="utf-8")
        source_patch = patch.object(audit, "LIBTIFF_SOURCE_SHA256", sha(b"source"))
        license_patch = patch.object(audit, "LIBTIFF_LICENSE_SHA256", sha(b"license"))
        source_patch.start()
        license_patch.start()
        self.addCleanup(source_patch.stop)
        self.addCleanup(license_patch.stop)

    def test_new_binary_uses_source_evidence_and_old_bytes_are_exact(self) -> None:
        rows = audit.build_rows(self.csv, self.graph, self.candidate, self.source, self.license)
        self.assertEqual(len(rows), 34)
        self.assertEqual(sum(row["source_kind"] == "UPSTREAM_SOURCE_BUILD" for row in rows), 1)
        self.assertTrue(all(row["release_obligations_reviewed"] == "NO" for row in rows))
        self.assertNotIn(audit.REMOVED_DLL, {row["binary"] for row in rows})

    def test_tampered_inherited_binary_and_source_are_rejected(self) -> None:
        inherited = self.candidate / "lib00.dll"
        inherited.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "candidate binary differs"):
            audit.build_rows(self.csv, self.graph, self.candidate, self.source, self.license)
        inherited.write_bytes(b"old:lib00.dll")
        self.source.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "source archive differs"):
            audit.build_rows(self.csv, self.graph, self.candidate, self.source, self.license)

    def test_old_graph_with_jbig_is_rejected(self) -> None:
        graph = json.loads(self.graph.read_text(encoding="utf-8"))
        graph["needed_local_files"].append(audit.REMOVED_DLL)
        self.graph.write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "static graph differs"):
            audit.build_rows(self.csv, self.graph, self.candidate, self.source, self.license)


if __name__ == "__main__":
    unittest.main()
