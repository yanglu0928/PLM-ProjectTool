from __future__ import annotations

import hashlib
import io
import sys
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_native_pe_license_materials import map_native  # noqa: E402


class NativePeMaterialTests(unittest.TestCase):
    def test_34_binary_map_keeps_generic_text_unattributed(self) -> None:
        binary_body = b"native"
        license_body = b"generic license"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for index in range(34):
                archive.writestr(f"payload/ocr/tesseract/a{index}.dll", binary_body)
            archive.writestr("payload/runtime/packages/unrelated.dist-info/licenses/LICENSE", license_body)
        rows = [{"binary": f"a{index}.dll", "binary_sha256": hashlib.sha256(binary_body).hexdigest(),
                 "source_kind": "MSYS2_PACKAGE_BYTES", "source_name": "sample",
                 "source_version": "1.0", "package_declared_license": "spdx:MIT",
                 "license_evidence_status": "PACKAGE_TEXT_HASH_VERIFIED",
                 "license_evidence_path": "upstream/LICENSE",
                 "license_evidence_sha256": hashlib.sha256(license_body).hexdigest(),
                 "release_obligations_reviewed": "NO"} for index in range(34)]
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            result = map_native(rows, archive)
        self.assertEqual(result["native_pe_count"], 34)
        self.assertEqual(result["candidate_legal_path_count"], 1)
        self.assertEqual(result["same_text_evidence_count"], 34)
        self.assertEqual(result["dedicated_native_notice_count"], 0)
        self.assertFalse(result["rows"][0]["dedicated_notice_present"])

    def test_missing_binary_rejected(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w"):
            pass
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive, self.assertRaisesRegex(ValueError, "byte identity"):
            map_native([{"binary": "a.dll", "release_obligations_reviewed": "NO"}], archive)

    def test_changed_binary_rejected(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("payload/ocr/tesseract/a.dll", b"actual")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive, self.assertRaisesRegex(ValueError, "byte identity"):
            map_native([{"binary": "a.dll", "binary_sha256": hashlib.sha256(b"wrong").hexdigest(),
                         "release_obligations_reviewed": "NO"}], archive)

    def test_dedicated_notice_boundary_rejected(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("payload/third-party-licenses/native-ocr/a/LICENSE", b"notice")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive, self.assertRaisesRegex(ValueError, "namespace changed"):
            map_native([], archive)


if __name__ == "__main__":
    unittest.main()
