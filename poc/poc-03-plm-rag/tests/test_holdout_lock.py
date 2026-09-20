from __future__ import annotations

import sys
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_lock import (  # noqa: E402
    HoldoutQuotaError,
    build_holdout_lock,
    collect_contaminated_chunk_ids,
)


def make_chunk(source: str, document: str, index: int, locator: str | None = None) -> dict:
    chunk_id = f"{source}-{document}-C-{index:016x}"
    return {
        "chunk_id": chunk_id,
        "document_id": f"{source}-{document}",
        "source_corpus": source,
        "text": f"候选内容 {source} {document} {index} " * 20,
        "text_sha256": f"{source}-{document}-{index}",
        "character_count": 300,
        "source_locators": [locator or f"word/paragraph/{index}"],
        "pages": [1],
        "sections": [],
    }


class HoldoutLockTests(unittest.TestCase):
    def test_contamination_union_includes_all_prior_exposure_channels(self) -> None:
        contaminated = collect_contaminated_chunk_ids(
            {"cases": [{"expected_relevant_chunk_ids": ["A"]}]},
            [{"contexts": [{"chunk_id": "B"}]}],
            {"cases": [{"candidate_chunks": [{"chunk_id": "C"}]}]},
            [{"top5_ids": ["D"], "reranker_top5_ids": ["E"]}],
        )
        self.assertEqual(contaminated, {"A", "B", "C", "D", "E"})

    def test_lock_is_deterministic_and_excludes_locator_overlap(self) -> None:
        quotas = {
            "STANDARD_CAPABILITY": 2,
            "CONTRACT": 1,
            "TECHNICAL_AGREEMENT": 1,
            "SURVEY": 1,
        }
        chunks = []
        for source, count in quotas.items():
            for index in range(1, count + 3):
                chunks.append(make_chunk(source, "SL-001", index))
        contaminated_chunk = make_chunk("STANDARD_CAPABILITY", "SL-001", 99, locator="shared")
        overlapping_chunk = make_chunk("STANDARD_CAPABILITY", "SL-001", 100, locator="shared")
        chunks.extend([contaminated_chunk, overlapping_chunk])
        first, report = build_holdout_lock(
            chunks,
            {contaminated_chunk["chunk_id"]},
            project_id="P",
            quotas=quotas,
        )
        second, _ = build_holdout_lock(
            chunks,
            {contaminated_chunk["chunk_id"]},
            project_id="P",
            quotas=quotas,
        )
        self.assertEqual(first["lock_fingerprint"], second["lock_fingerprint"])
        self.assertEqual(len(first["candidates"]), 5)
        self.assertNotIn(overlapping_chunk["chunk_id"], {item["chunk_id"] for item in first["candidates"]})
        self.assertTrue(report["checks"]["selected_chunk_ids_disjoint"])

    def test_unsatisfied_quota_fails_closed(self) -> None:
        with self.assertRaisesRegex(HoldoutQuotaError, "quotas cannot be satisfied"):
            build_holdout_lock(
                [make_chunk("SURVEY", "SL-001", 1)],
                set(),
                project_id="P",
                quotas={"SURVEY": 2},
            )


if __name__ == "__main__":
    unittest.main()
