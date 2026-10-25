from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.action_list_import import (  # noqa: E402
    ACTION_HEADERS,
    import_action_list,
)


def candidate(index: int) -> dict:
    candidate_id = f"GD-C-{index:04d}"
    chunk_id = f"CONTRACT-SL-001-C-{index:04d}"
    return {
        "candidate_id": candidate_id,
        "source_corpus": "CONTRACT",
        "scope": "PROJECT",
        "project_id": "PROJECT-A",
        "expected_relevant_chunk_ids": [chunk_id],
        "expected_citations": [
            {
                "document_id": "CONTRACT-SL-001",
                "chunk_id": chunk_id,
                "source_locators": [f"word/paragraph/{index}"],
            }
        ],
        "candidate_content": f"候选正文 {index}",
        "candidate_content_sha256": f"{index:064x}",
    }


def task(record: dict) -> dict:
    citation = record["expected_citations"][0]
    suffix = record["candidate_id"].removeprefix("GD-C-")
    return {
        "task_id": f"CONF-{suffix}",
        "candidate_id": record["candidate_id"],
        "source_corpus": record["source_corpus"],
        "source_type": "CONTRACT",
        "classification": "STANDARD_SATISFIED",
        "ai_finding": "系统是否支持受控审批？",
        "answer_terms": "受控审批；状态追溯",
        "confirmed_locator": citation["source_locators"][0],
        "document_id": citation["document_id"],
        "chunk_id": citation["chunk_id"],
        "candidate_content_sha256": record["candidate_content_sha256"],
    }


def write_action_list(path: Path, rows: list[list]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "确认清单"
    for _ in range(7):
        sheet.append([])
    sheet.append(ACTION_HEADERS)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


def action_row(item: dict, decision: str, note: str = "") -> list:
    return [
        item["task_id"],
        item["source_corpus"],
        "低",
        item["ai_finding"],
        "建议标记为标准满足",
        "打开证据",
        decision,
        note,
        "人工审核员",
        datetime(2026, 9, 18),
        "",
    ]


class ActionListImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_agreed_ai_suggestion_builds_approved_case(self) -> None:
        record = candidate(1)
        item = task(record)
        workbook_path = self.root / "actions.xlsx"
        write_action_list(workbook_path, [action_row(item, "同意AI建议")])

        result = import_action_list(workbook_path, [record], [item])

        self.assertFalse(result.has_errors)
        self.assertEqual(1, len(result.cases))
        self.assertEqual("GD-0001", result.cases[0]["case_id"])
        self.assertEqual(1, result.status_counts["APPROVED"])

    def test_deferred_action_is_not_approved(self) -> None:
        record = candidate(1)
        item = task(record)
        workbook_path = self.root / "actions.xlsx"
        write_action_list(workbook_path, [action_row(item, "暂不处理")])

        result = import_action_list(workbook_path, [record], [item])

        self.assertFalse(result.has_errors)
        self.assertEqual([], result.cases)
        self.assertEqual(1, result.status_counts["PENDING"])

    def test_modified_confirmation_requires_substantive_conclusion(self) -> None:
        record = candidate(1)
        item = task(record)
        workbook_path = self.root / "actions.xlsx"
        write_action_list(workbook_path, [action_row(item, "修改后确认", "修改结论")])

        result = import_action_list(workbook_path, [record], [item])

        self.assertIn(
            "MODIFIED_CONCLUSION_INCOMPLETE",
            {issue.code for issue in result.issues},
        )
        self.assertEqual([], result.cases)
        self.assertEqual(1, result.status_counts["APPROVED"])

    def test_substantive_modified_confirmation_builds_approved_case(self) -> None:
        record = candidate(1)
        item = task(record)
        workbook_path = self.root / "actions.xlsx"
        conclusion = (
            "人工复核：原文和证据已经完成核对，技术字段与来源保持一致。"
            "结论：按修改后的业务说明确认，并纳入本轮质量真值。"
        )
        write_action_list(
            workbook_path,
            [action_row(item, "修改后确认", conclusion)],
        )

        result = import_action_list(workbook_path, [record], [item])

        self.assertFalse(result.has_errors)
        self.assertEqual(1, len(result.cases))
        self.assertEqual("GD-0001", result.cases[0]["case_id"])
        self.assertEqual(1, result.status_counts["APPROVED"])

    def test_modified_conclusion_can_resolve_insufficient_information(self) -> None:
        record = candidate(1)
        item = task(record)
        item["classification"] = "HUMAN_CONFIRMATION_REQUIRED"
        workbook_path = self.root / "actions.xlsx"
        conclusion = (
            "人工复核：当前证据片段不足，尚不能支持完整业务判断。"
            "结论：保留为信息不足，待补充上下文后再确认。"
        )
        write_action_list(
            workbook_path,
            [action_row(item, "修改后确认", conclusion)],
        )

        result = import_action_list(workbook_path, [record], [item])

        self.assertFalse(result.has_errors)
        self.assertEqual(
            "INSUFFICIENT_INFORMATION",
            result.cases[0]["expected_classification"],
        )

    def test_modified_conclusion_can_resolve_no_reliable_match(self) -> None:
        record = candidate(1)
        item = task(record)
        item["classification"] = "HUMAN_CONFIRMATION_REQUIRED"
        workbook_path = self.root / "actions.xlsx"
        conclusion = (
            "人工复核：当前抽取内容更像缩写、编号或OCR片段。"
            "结论：暂不作为独立需求项，未发现可靠业务匹配。"
        )
        write_action_list(
            workbook_path,
            [action_row(item, "修改后确认", conclusion)],
        )

        result = import_action_list(workbook_path, [record], [item])

        self.assertFalse(result.has_errors)
        self.assertEqual(
            "NO_RELIABLE_MATCH",
            result.cases[0]["expected_classification"],
        )

    def test_changed_question_is_rejected(self) -> None:
        record = candidate(1)
        item = task(record)
        row = action_row(item, "同意AI建议")
        row[3] = "被修改的问题"
        workbook_path = self.root / "actions.xlsx"
        write_action_list(workbook_path, [row])

        result = import_action_list(workbook_path, [record], [item])

        self.assertIn("SOURCE_FIELD_CHANGED", {issue.code for issue in result.issues})
        self.assertEqual([], result.cases)


if __name__ == "__main__":
    unittest.main()
