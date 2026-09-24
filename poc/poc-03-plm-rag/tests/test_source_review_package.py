from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "build_source_review_package.py"
)
SPEC = importlib.util.spec_from_file_location("build_source_review_package", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceReviewPackageTests(unittest.TestCase):
    def test_mapping_normalizes_labels(self) -> None:
        result = MODULE._mapping(["survey=C:/data/survey"], option="--source-root")

        self.assertEqual(Path("C:/data/survey"), result["SURVEY"])

    def test_parsed_document_uses_corpus_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SL-001.parsed.json").write_text(
                '{"source":{"file_name":"manual.docx"}}',
                encoding="utf-8",
            )

            result = MODULE._parsed_document(
                "STANDARD_CAPABILITY-SL-001",
                {"STANDARD_CAPABILITY": root},
            )

        self.assertEqual("manual.docx", result["source"]["file_name"])

    def test_review_rows_remain_pending(self) -> None:
        rows = MODULE._review_rows(
            [
                {
                    "candidate_id": "GD-C-0001",
                    "query": "问题",
                    "source_type": "SURVEY",
                    "classification": "HUMAN_CONFIRMATION_REQUIRED",
                    "answer_terms": ["术语"],
                    "citation_locators": ["docx/paragraphs/1"],
                }
            ]
        )

        self.assertEqual("PENDING", rows[0]["review_status"])
        self.assertEqual("术语", rows[0]["answer_terms"])


if __name__ == "__main__":
    unittest.main()
