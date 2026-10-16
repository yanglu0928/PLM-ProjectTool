from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_notice_draft_inputs import summarize_python  # noqa: E402


class NoticeDraftInputTests(unittest.TestCase):
    def test_first_party_separated_and_missing_material_reported(self) -> None:
        rows = [
            {"name": "plm-project-tool-backend", "version": "0.1.0.dev0",
             "notice_files": [], "notice_file_count": 0, "license_expression": ""},
            {"name": "External", "version": "1.0", "notice_files": [],
             "notice_file_count": 0, "license_expression": ""},
            {"name": "Other", "version": "2.0", "notice_files": ["Other.dist-info/LICENSE"],
             "notice_file_count": 1, "license_expression": "MIT"},
        ]
        names = {"payload/runtime/packages/Other.dist-info/LICENSE"}
        result = summarize_python(rows, names)
        self.assertEqual(result["third_party_distribution_count"], 2)
        self.assertEqual(result["third_party_missing_license_expression_names"], ["External"])
        self.assertEqual(result["third_party_no_notice_material_names"], ["External"])

    def test_separate_wheel_sidecar_counts_as_existing_material(self) -> None:
        rows = [{"name": "plm-project-tool-backend", "version": "0.1.0.dev0",
                 "notice_files": [], "notice_file_count": 0},
                {"name": "et_xmlfile", "version": "2.0.0",
                 "notice_files": [], "notice_file_count": 0}]
        names = {"payload/third-party-licenses/notices/et_xmlfile-2.0.0-py3-none-any.whl/LICENCE.rst"}
        result = summarize_python(rows, names)
        self.assertEqual(result["third_party_no_notice_material_names"], [])

    def test_declared_notice_absence_rejected(self) -> None:
        rows = [{"name": "plm-project-tool-backend", "version": "0.1.0.dev0",
                 "notice_files": [], "notice_file_count": 0},
                {"name": "External", "version": "1.0",
                 "notice_files": ["missing/LICENSE"], "notice_file_count": 1}]
        with self.assertRaisesRegex(ValueError, "notice missing"):
            summarize_python(rows, set())


if __name__ == "__main__":
    unittest.main()
