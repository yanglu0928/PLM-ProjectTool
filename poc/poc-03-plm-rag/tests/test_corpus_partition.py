from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.corpus_partition import (  # noqa: E402
    classify_library_document,
    partition_parsed_documents,
)


class CorpusPartitionTests(unittest.TestCase):
    def test_standard_library_separates_survey_form(self) -> None:
        self.assertEqual(
            "SURVEY",
            classify_library_document(
                library_kind="STANDARD_LIBRARY", file_name="系统调研业务表单V1.0.docx"
            ),
        )
        self.assertEqual(
            "STANDARD_CAPABILITY",
            classify_library_document(
                library_kind="STANDARD_LIBRARY", file_name="系统用户手册.docx"
            ),
        )

    def test_contract_library_uses_explicit_document_title(self) -> None:
        self.assertEqual(
            "TECHNICAL_AGREEMENT",
            classify_library_document(
                library_kind="CONTRACT_LIBRARY", file_name="PLM技术协议.docx"
            ),
        )
        self.assertEqual(
            "CONTRACT",
            classify_library_document(
                library_kind="CONTRACT_LIBRARY", file_name="软件采购合同.docx"
            ),
        )

    def test_partition_copies_only_passed_parsed_documents(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poc03-partition-") as temp_dir:
            root = Path(temp_dir)
            parsed = root / "parsed"
            output = root / "output"
            parsed.mkdir()
            (parsed / "SL-001.parsed.json").write_text(
                json.dumps({"schema_version": "poc-05.1"}), encoding="utf-8"
            )
            counts = partition_parsed_documents(
                [
                    {
                        "document_id": "SL-001",
                        "relative_path": "系统用户手册.docx",
                        "parsed_output": "SL-001.parsed.json",
                        "status": "PASS",
                    },
                    {
                        "document_id": "SL-002",
                        "relative_path": "忽略.docx",
                        "parsed_output": "SL-002.parsed.json",
                        "status": "FAIL_PARSE",
                    },
                ],
                parsed_dir=parsed,
                output_root=output,
                library_kind="STANDARD_LIBRARY",
            )
            self.assertEqual({"STANDARD_CAPABILITY": 1}, counts)
            self.assertTrue(
                (output / "STANDARD_CAPABILITY" / "SL-001.parsed.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
