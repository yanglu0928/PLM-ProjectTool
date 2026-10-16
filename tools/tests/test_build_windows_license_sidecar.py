from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("license_sidecar", TOOLS / "build_windows_license_sidecar.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LicenseSidecarTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        wheel = wheelhouse / "example_pkg-1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("example_pkg-1.0.dist-info/METADATA", "Name: example-pkg\nVersion: 1.0\nLicense: MIT\n")
            archive.writestr("example_pkg-1.0.dist-info/licenses/LICENSE", b"synthetic text")
        hashes = root / "sha256sums.txt"
        hashes.write_text(f"{MODULE.digest_file(wheel)}  {wheel.name}\n", encoding="ascii")
        candidate = root / "candidate.zip"
        with zipfile.ZipFile(candidate, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"release_eligible": False, "vendored_distribution_count": 1}))
            archive.writestr("third-party-inventory.json", json.dumps({"status": "REVIEW_REQUIRED", "distribution_count": 1, "distributions": [{"name": "example-pkg", "version": "1.0"}]}))
        return candidate, wheelhouse, hashes

    def test_sidecar_preserves_exact_notice_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, wheelhouse, hashes = self._fixture(root)
            output = root / "sidecar.zip"
            result = MODULE.build_sidecar(candidate, wheelhouse, hashes, output)
            self.assertEqual(result["notice_file_count"], 1)
            self.assertFalse(result["release_eligible"])
            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["review_status"], "REVIEW_REQUIRED")
                self.assertEqual(archive.read(manifest["files"][0]["path"]), b"synthetic text")
            with self.assertRaisesRegex(ValueError, "overwrite"):
                MODULE.build_sidecar(candidate, wheelhouse, hashes, output)

    def test_tampered_wheel_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate, wheelhouse, hashes = self._fixture(root)
            (wheelhouse / "example_pkg-1.0-py3-none-any.whl").write_bytes(b"tampered")
            output = root / "sidecar.zip"
            with self.assertRaisesRegex(ValueError, "wheel hash mismatch"):
                MODULE.build_sidecar(candidate, wheelhouse, hashes, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
