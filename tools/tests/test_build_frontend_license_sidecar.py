from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.tests import test_audit_frontend_bundle_licenses as fixture_module


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("frontend_sidecar", TOOLS / "build_frontend_license_sidecar.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendSidecarTests(unittest.TestCase):
    def test_exact_notices_preserved_and_not_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture_module.FrontendLicenseAuditTests()._fixture(root)
            output = root / "frontend-sidecar.zip"
            result = MODULE.build_sidecar(root, output)
            self.assertEqual(result["package_count"], 2)
            self.assertEqual(result["license_file_count"], 2)
            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                self.assertFalse(manifest["release_eligible"])
                self.assertEqual(manifest["review_status"], "REVIEW_REQUIRED")
                self.assertEqual(len(manifest["files"]), 2)
                for item in manifest["files"]:
                    self.assertEqual(MODULE.sha256(archive.read(item["path"])), item["sha256"])
            with self.assertRaisesRegex(ValueError, "overwrite"):
                MODULE.build_sidecar(root, output)

    def test_missing_license_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = fixture_module.FrontendLicenseAuditTests()._fixture(root)
            (app / "node_modules" / "facade" / "LICENSE").unlink()
            output = root / "frontend-sidecar.zip"
            with self.assertRaisesRegex(ValueError, "license file missing"):
                MODULE.build_sidecar(root, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
