from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_python_declared_license_materials import map_declared  # noqa: E402


def fixture(*, expression: str = "MIT", header: str = "LICENSE",
            include_notice: bool = True) -> tuple[list[dict], zipfile.ZipFile]:
    row = {"name": "alpha", "version": "1.0", "license_expression": "MIT",
           "notice_files": ["alpha-1.0.dist-info/licenses/LICENSE"],
           "notice_file_count": 1, "license_classifiers": [], "review_status": "REVIEW_REQUIRED"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("payload/runtime/packages/alpha-1.0.dist-info/METADATA",
                         f"Name: alpha\nVersion: 1.0\nLicense-Expression: {expression}\nLicense-File: {header}\n")
        if include_notice:
            archive.writestr("payload/runtime/packages/alpha-1.0.dist-info/licenses/LICENSE", "license")
    buffer.seek(0)
    return [row], zipfile.ZipFile(buffer)


class DeclaredLicenseMaterialsTests(unittest.TestCase):
    def test_exact_expression_header_and_file_remain_review_required(self) -> None:
        rows, archive = fixture()
        with archive:
            mapped = map_declared(rows, archive)
        self.assertEqual(mapped[0]["license_expression"], "MIT")
        self.assertEqual(mapped[0]["license_file_headers"], ["LICENSE"])
        self.assertEqual(mapped[0]["review_status"], "REVIEW_REQUIRED")

    def test_expression_mismatch_rejected(self) -> None:
        rows, archive = fixture(expression="Apache-2.0")
        with archive, self.assertRaisesRegex(ValueError, "expression differs"):
            map_declared(rows, archive)

    def test_missing_notice_rejected(self) -> None:
        rows, archive = fixture(include_notice=False)
        with archive, self.assertRaisesRegex(ValueError, "inventory differs"):
            map_declared(rows, archive)

    def test_unmapped_license_header_rejected(self) -> None:
        rows, archive = fixture(header="OTHER")
        with archive, self.assertRaisesRegex(ValueError, "no exact notice"):
            map_declared(rows, archive)


if __name__ == "__main__":
    unittest.main()
