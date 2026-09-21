from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(POC_DIR / "scripts"))

from validate_live_quality_metrics import (  # noqa: E402
    FULL_TEXT_SQL,
    RETRIEVAL_PIPELINE_VERSION,
    VECTOR_SQL,
    _deduplicate_chunks,
    _load_complete_embeddings,
    _load_prediction_cache,
    _retrieval_cache_is_current,
    _sha256,
    _validate_evaluation_dataset_size,
)


class LiveQualityRetrievalContractTests(unittest.TestCase):
    def test_identical_duplicate_chunks_are_deduplicated(self) -> None:
        chunk = {"chunk_id": "C-1", "text": "same", "source_locators": ["L1"]}
        self.assertEqual([chunk], _deduplicate_chunks([chunk, dict(chunk)]))

    def test_conflicting_duplicate_chunk_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "conflicting duplicate ChunkId"):
            _deduplicate_chunks(
                [
                    {"chunk_id": "C-1", "text": "first"},
                    {"chunk_id": "C-1", "text": "second"},
                ]
            )

    def test_holdout_requires_exactly_fifty_cases(self) -> None:
        dataset = {
            "schema_version": "poc-03.holdout.v1",
            "cases": [{} for _ in range(50)],
        }
        self.assertEqual(
            "independent_holdout", _validate_evaluation_dataset_size(dataset)
        )
        dataset["cases"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 50"):
            _validate_evaluation_dataset_size(dataset)

    def test_golden_dataset_keeps_original_size_contract(self) -> None:
        self.assertEqual(
            "golden_dataset",
            _validate_evaluation_dataset_size({"cases": [{} for _ in range(100)]}),
        )
        with self.assertRaisesRegex(ValueError, "100 to 200"):
            _validate_evaluation_dataset_size({"cases": [{} for _ in range(50)]})

    def test_live_queries_require_parameterized_source_type_filter(self) -> None:
        for sql in (VECTOR_SQL, FULL_TEXT_SQL):
            self.assertIn("source_corpus = %(source_type)s", sql)
            self.assertIn("project_id = %(project_id)s", sql)

    def test_only_current_source_aware_cache_is_reused(self) -> None:
        self.assertFalse(
            _retrieval_cache_is_current(None, source_type="CONTRACT")
        )
        self.assertFalse(
            _retrieval_cache_is_current(
                {"pipeline_version": "legacy", "source_type": "CONTRACT"},
                source_type="CONTRACT",
            )
        )
        self.assertFalse(
            _retrieval_cache_is_current(
                {"pipeline_version": RETRIEVAL_PIPELINE_VERSION},
                source_type="CONTRACT",
            )
        )
        self.assertFalse(
            _retrieval_cache_is_current(
                {
                    "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
                    "source_type": "SURVEY",
                },
                source_type="CONTRACT",
            )
        )
        self.assertTrue(
            _retrieval_cache_is_current(
                {
                    "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
                    "source_type": "CONTRACT",
                },
                source_type="CONTRACT",
            )
        )

    def test_retrieval_only_requires_complete_hash_matched_embedding_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "id": "C-1",
                        "text_sha256": _sha256("evidence"),
                        "vector": [0.1, 0.2],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                {"C-1": [0.1, 0.2]},
                _load_complete_embeddings(
                    [("C-1", "evidence")], cache_path=path, dimension=2
                ),
            )
            with self.assertRaises(RuntimeError):
                _load_complete_embeddings(
                    [("C-1", "changed")], cache_path=path, dimension=2
                )

    def test_prediction_cache_is_bound_to_prompt_v2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction-cache.jsonl"
            rows = [
                {"case_id": "OLD", "prompt_id": "poc03-quality", "prompt_version": "v1"},
                {"case_id": "CURRENT", "prompt_id": "poc03-quality", "prompt_version": "v2"},
                {"case_id": "MISSING"},
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )
            self.assertEqual({"CURRENT"}, set(_load_prediction_cache(path)))


if __name__ == "__main__":
    unittest.main()
