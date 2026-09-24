from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = POC_DIR / "scripts" / "build_project_analysis_package.py"
SPEC = importlib.util.spec_from_file_location("project_analysis_package", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProjectAnalysisPackageTests(unittest.TestCase):
    def test_compact_text_removes_repeated_table_cells(self) -> None:
        text = "需求内容 | 需求内容 | 需求内容 | 下一项"
        self.assertEqual("需求内容 | 下一项", MODULE.compact_text(text))

    def test_file_url_encodes_unicode_without_losing_drive(self) -> None:
        url = MODULE.file_url(Path("D:/资料库/示例 文件.docx"))
        self.assertTrue(url.startswith("file:///D:/"))
        self.assertIn("%E8%B5%84%E6%96%99%E5%BA%93", url)
        self.assertIn("%20", url)

    def test_project_alias_matching_is_filename_based(self) -> None:
        document = MODULE.SourceDocument(
            source_type="ACTUAL_SURVEY",
            file_name="2026-01-01【示例项目】调研记录.docx",
            original_path=None,
            parsed_path=Path("sample.json"),
            blocks=[],
            warnings=[],
        )
        self.assertTrue(MODULE.belongs_to(document, ["示例项目"]))
        self.assertFalse(MODULE.belongs_to(document, ["其他项目"]))

    def test_actual_survey_has_higher_evidence_priority_than_solution(self) -> None:
        block = {"text": "物料 BOM 变更", "source_locator": "word/paragraph/1"}
        survey_score = MODULE.block_score(
            block, ["BOM", "变更"], MODULE.SOURCE_PRIORITY["ACTUAL_SURVEY"]
        )
        solution_score = MODULE.block_score(
            block, ["BOM", "变更"], MODULE.SOURCE_PRIORITY["SOLUTION"]
        )
        self.assertGreater(survey_score, solution_score)


if __name__ == "__main__":
    unittest.main()
