from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.review_import import (  # noqa: E402
    HEADERS,
    build_golden_dataset,
    build_sanitized_import_report,
    import_review_workbook,
)


def candidate(index: int) -> dict:
    candidate_id = f"GD-C-{index:04d}"
    chunk_id = f"DOC-001-C-{index:04d}"
    content = f"候选正文 {index}"
    return {
        "candidate_id": candidate_id,
        "source_corpus": "CONTRACT",
        "scope": "PROJECT",
        "project_id": "PROJECT-A",
        "expected_relevant_chunk_ids": [chunk_id],
        "expected_citations": [
            {
                "document_id": "DOC-001",
                "chunk_id": chunk_id,
                "source_locators": [f"word/paragraph/{index}"],
            }
        ],
        "candidate_content": content,
        "candidate_content_sha256": f"{index:064x}",
    }


def review_row(record: dict, *, status: str = "APPROVED") -> list:
    citation = record["expected_citations"][0]
    return [
        record["candidate_id"],
        record["source_corpus"],
        record["scope"],
        record["project_id"],
        citation["document_id"],
        citation["chunk_id"],
        "；".join(citation["source_locators"]),
        record["candidate_content"],
        record["candidate_content_sha256"],
        "系统是否支持受控审批？",
        "CONTRACT",
        "STANDARD_SATISFIED",
        "受控审批；状态追溯",
        citation["source_locators"][0],
        status,
        "人工审核员",
        datetime(2026, 9, 17, 9, 0),
        "",
        "可转正式集" if status == "APPROVED" else "待评审",
    ]


def write_workbook(path: Path, records: list[dict], rows: list[list] | None = None) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "候选评审"
    sheet.append([])
    sheet.append(["POC-03 候选评审明细"])
    sheet.append([])
    sheet.append([])
    sheet.append(HEADERS)
    for row in rows if rows is not None else [review_row(record) for record in records]:
        sheet.append(row)
    workbook.save(path)
    workbook.close()


class ReviewImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.schema = json.loads(
            (POC_DIR / "schema" / "golden-dataset.schema.json").read_text(encoding="utf-8")
        )

    def test_100_approved_rows_build_schema_valid_dataset(self) -> None:
        records = [candidate(index) for index in range(1, 101)]
        workbook_path = self.root / "review.xlsx"
        write_workbook(workbook_path, records)
        result = import_review_workbook(workbook_path, records)
        self.assertFalse(result.has_errors)
        self.assertEqual(100, len(result.cases))
        dataset = build_golden_dataset(
            result,
            dataset_id="POC03-GD-001",
            provider="test-provider",
            model="test-model",
            dimension=3,
            index_version="idx-001",
            schema=self.schema,
        )
        self.assertEqual("GD-0001", dataset["cases"][0]["case_id"])
        self.assertEqual("2026-09-17T01:00:00Z", dataset["cases"][0]["review"]["reviewed_at"])

    def test_pending_rows_are_not_exported_and_report_is_incomplete(self) -> None:
        records = [candidate(index) for index in range(1, 3)]
        workbook_path = self.root / "review.xlsx"
        write_workbook(
            workbook_path,
            records,
            [review_row(record, status="PENDING") for record in records],
        )
        result = import_review_workbook(workbook_path, records)
        report = build_sanitized_import_report(
            result,
            generated_at="2026-09-17T00:00:00Z",
            output_written=False,
        )
        self.assertFalse(result.has_errors)
        self.assertEqual([], result.cases)
        self.assertEqual("INCOMPLETE", report["status"])

    def test_changed_candidate_content_is_rejected(self) -> None:
        record = candidate(1)
        row = review_row(record)
        row[7] = "被修改的候选正文"
        workbook_path = self.root / "review.xlsx"
        write_workbook(workbook_path, [record], [row])
        result = import_review_workbook(workbook_path, [record])
        self.assertIn("SOURCE_FIELD_CHANGED", {issue.code for issue in result.issues})
        self.assertEqual([], result.cases)

    def test_citation_outside_candidate_source_is_rejected(self) -> None:
        record = candidate(1)
        row = review_row(record)
        row[13] = "word/paragraph/999"
        workbook_path = self.root / "review.xlsx"
        write_workbook(workbook_path, [record], [row])
        result = import_review_workbook(workbook_path, [record])
        self.assertIn("CITATION_OUTSIDE_SOURCE", {issue.code for issue in result.issues})
        self.assertEqual([], result.cases)

    def test_approved_row_with_missing_reviewer_is_rejected(self) -> None:
        record = candidate(1)
        row = review_row(record)
        row[15] = ""
        workbook_path = self.root / "review.xlsx"
        write_workbook(workbook_path, [record], [row])
        result = import_review_workbook(workbook_path, [record])
        self.assertIn("APPROVED_FIELD_MISSING", {issue.code for issue in result.issues})
        self.assertEqual([], result.cases)

    def test_approved_query_must_have_two_characters(self) -> None:
        record = candidate(1)
        row = review_row(record)
        row[9] = "问"
        workbook_path = self.root / "review.xlsx"
        write_workbook(workbook_path, [record], [row])
        result = import_review_workbook(workbook_path, [record])
        self.assertIn("QUERY_TOO_SHORT", {issue.code for issue in result.issues})
        self.assertEqual([], result.cases)


if __name__ == "__main__":
    unittest.main()
