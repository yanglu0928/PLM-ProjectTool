from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "license_audit", Path(__file__).resolve().parents[1] / "audit_windows_candidate_licenses.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LicenseAuditTests(unittest.TestCase):
    def test_notice_detection_excludes_product_code_and_accepts_license_directory(self) -> None:
        self.assertFalse(MODULE._notice("plm_assistant/license_validation.py"))
        self.assertTrue(MODULE._notice("package-1.0.dist-info/licenses/BUILD_LICENSES/pdfium.txt"))

    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        wheel = wheelhouse / "example_pkg-1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("example_pkg-1.0.dist-info/METADATA", "Name: example-pkg\nVersion: 1.0\nLicense: Apache License 2.0\n")
            archive.writestr("example_pkg-1.0.dist-info/licenses/LICENSE", "synthetic license")
        hash_manifest = root / "sha256sums.txt"
        hash_manifest.write_text(f"{MODULE.digest_file(wheel)}  {wheel.name}\n", encoding="ascii")
        candidate = root / "candidate.zip"
        with zipfile.ZipFile(candidate, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"release_eligible": False, "vendored_distribution_count": 1}))
            archive.writestr("third-party-inventory.json", json.dumps({"status": "REVIEW_REQUIRED", "distribution_count": 1, "distributions": [{"name": "example-pkg", "version": "1.0"}]}))
        return candidate, wheelhouse, hash_manifest

    def test_exact_wheel_evidence_never_clears_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, wheelhouse, hashes = self._fixture(Path(temp))
            result = MODULE.audit(candidate, wheelhouse, hashes)
            self.assertEqual(result["wheel_count"], 1)
            self.assertEqual(result["notice_file_package_count"], 1)
            self.assertEqual(result["packages"][0]["legacy_license"], "Apache License 2.0")
            self.assertEqual(result["packages"][0]["notice_files"][0]["sha256"], MODULE.digest_bytes(b"synthetic license"))
            self.assertFalse(result["release_eligible"])

    def test_tampered_wheel_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, wheelhouse, hashes = self._fixture(Path(temp))
            (wheelhouse / "example_pkg-1.0-py3-none-any.whl").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "wheel hash mismatch"):
                MODULE.audit(candidate, wheelhouse, hashes)

    def test_identity_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, wheelhouse, hashes = self._fixture(Path(temp))
            with zipfile.ZipFile(candidate, "w") as archive:
                archive.writestr("manifest.json", json.dumps({"release_eligible": False, "vendored_distribution_count": 1}))
                archive.writestr("third-party-inventory.json", json.dumps({"status": "REVIEW_REQUIRED", "distribution_count": 1, "distributions": [{"name": "wrong", "version": "1.0"}]}))
            with self.assertRaisesRegex(ValueError, "identities differ"):
                MODULE.audit(candidate, wheelhouse, hashes)

    def test_release_claim_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, wheelhouse, hashes = self._fixture(Path(temp))
            with zipfile.ZipFile(candidate, "w") as archive:
                archive.writestr("manifest.json", json.dumps({"release_eligible": True, "vendored_distribution_count": 1}))
                archive.writestr("third-party-inventory.json", json.dumps({"status": "REVIEW_REQUIRED", "distribution_count": 1, "distributions": [{"name": "example-pkg", "version": "1.0"}]}))
            with self.assertRaisesRegex(ValueError, "release gate rejected"):
                MODULE.audit(candidate, wheelhouse, hashes)


if __name__ == "__main__":
    unittest.main()
