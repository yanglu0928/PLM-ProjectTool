from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.evidence_selector import (  # noqa: E402
    rank_evidence_support,
    select_primary_evidence,
)


class EvidenceSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = {
            "C-1": {
                "scope": "PROJECT",
                "project_id": "P-1",
                "source_corpus": "STANDARD_CAPABILITY",
                "text": "通用项目管理说明。",
            },
            "C-2": {
                "scope": "PROJECT",
                "project_id": "P-1",
                "source_corpus": "STANDARD_CAPABILITY",
                "text": "服务器宕机后支持强制重新排队并回到未分配队列。",
            },
        }

    def test_direct_support_can_beat_first_retrieval_position(self) -> None:
        selected = select_primary_evidence(
            "服务器宕机后是否支持强制重新排队？",
            ["C-1", "C-2"],
            self.chunks,
            project_id="P-1",
        )
        self.assertEqual("C-2", selected)

    def test_rank_output_keeps_original_rank_for_audit(self) -> None:
        ranked = rank_evidence_support(
            "强制重新排队",
            ["C-1", "C-2"],
            self.chunks,
            project_id="P-1",
        )
        self.assertEqual(2, ranked[0]["original_rank"])
        self.assertGreater(ranked[0]["support_score"], ranked[1]["support_score"])

    def test_cross_project_chunk_fails_closed(self) -> None:
        self.chunks["C-2"]["project_id"] = "P-2"
        with self.assertRaisesRegex(ValueError, "another ProjectId"):
            rank_evidence_support(
                "强制重新排队",
                ["C-2"],
                self.chunks,
                project_id="P-1",
            )
