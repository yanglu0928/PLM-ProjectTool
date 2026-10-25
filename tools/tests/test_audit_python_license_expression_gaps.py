from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_python_license_expression_gaps import map_gaps  # noqa: E402


def candidate(rows: list[dict], metadata: str, sidecar: bool = False) -> tuple[list[dict], zipfile.ZipFile]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("payload/runtime/packages/alpha-1.0.dist-info/METADATA", metadata)
        for row in rows:
            for path in row.get("notice_files", []):
                archive.writestr("payload/runtime/packages/" + path, "text")
        if sidecar:
            archive.writestr("payload/third-party-licenses/notices/alpha-1.0-py3-none-any.whl/LICENSE", "text")
    buffer.seek(0)
    return rows, zipfile.ZipFile(buffer)


class PythonLicenseGapMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {"name": "alpha", "version": "1.0", "license_expression": "",
                    "license_classifiers": [], "notice_files": [], "notice_file_count": 0,
                    "review_status": "REVIEW_REQUIRED"}

    def test_no_notice_remains_review_required(self) -> None:
        rows, archive = candidate([self.row], "Name: alpha\nVersion: 1.0\nLicense: Apache-2.0\n")
        with archive:
            mapped = map_gaps(rows, archive)
        self.assertEqual(mapped[0]["material_class"], "NO_DISTRIBUTION_NOTICE")
        self.assertTrue(mapped[0]["legacy_license_field_present"])
        self.assertEqual(mapped[0]["review_status"], "REVIEW_REQUIRED")

    def test_embedded_and_sidecar_are_distinct(self) -> None:
        row = {**self.row, "notice_files": ["alpha-1.0.dist-info/LICENSE"], "notice_file_count": 1}
        rows, archive = candidate([row], "Name: alpha\nVersion: 1.0\n", True)
        with archive:
            mapped = map_gaps(rows, archive)
        self.assertEqual(mapped[0]["material_class"], "EMBEDDED")
        self.assertEqual(len(mapped[0]["sidecar_paths"]), 1)

    def test_sidecar_only(self) -> None:
        rows, archive = candidate([self.row], "Name: alpha\nVersion: 1.0\n", True)
        with archive:
            mapped = map_gaps(rows, archive)
        self.assertEqual(mapped[0]["material_class"], "SIDECAR_ONLY")

    def test_nonblank_metadata_expression_rejected(self) -> None:
        rows, archive = candidate([self.row], "Name: alpha\nVersion: 1.0\nLicense-Expression: MIT\n")
        with archive, self.assertRaisesRegex(ValueError, "boundary differs"):
            map_gaps(rows, archive)

    def test_missing_declared_embedded_notice_rejected(self) -> None:
        rows, archive = candidate([self.row], "Name: alpha\nVersion: 1.0\n")
        rows[0]["notice_files"] = ["alpha-1.0.dist-info/LICENSE"]
        rows[0]["notice_file_count"] = 1
        with archive, self.assertRaisesRegex(ValueError, "notice missing"):
            map_gaps(rows, archive)


if __name__ == "__main__":
    unittest.main()
