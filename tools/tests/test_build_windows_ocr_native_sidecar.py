from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_windows_ocr_native_sidecar as native


class NativeSidecarSafetyTests(unittest.TestCase):
    def test_entry_requires_ascii_safe_relative_path(self) -> None:
        root = Path("C:/safe")
        self.assertEqual(native._entry("tesseract", root / "bin" / "tesseract.exe", root),
                         "payload/ocr/tesseract/bin/tesseract.exe")
        with self.assertRaisesRegex(ValueError, "path rejected"):
            native._entry("models", root / "中文" / "model.bin", root)

    def test_verifier_rejects_traversal_and_release_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.object(native, "EXPECTED_FILES", 1):
            traversal = Path(temp) / "traversal.zip"
            with zipfile.ZipFile(traversal, "x") as archive:
                archive.writestr("manifest.json", b"{}")
                archive.writestr("../escape", b"bad")
            with self.assertRaisesRegex(ValueError, "path rejected"):
                native.verify(traversal)
            release = Path(temp) / "release.zip"
            with zipfile.ZipFile(release, "x") as archive:
                archive.writestr("manifest.json", json.dumps({
                    "kind": "WINDOWS11_OCR_NATIVE_NON_RELEASE", "release_eligible": True,
                    "license_status": "REVIEW_REQUIRED", "files": {"payload/ocr/test": {}}}))
                archive.writestr("payload/ocr/test", b"data")
            with self.assertRaisesRegex(ValueError, "manifest rejected"):
                native.verify(release)


if __name__ == "__main__":
    unittest.main()
