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
    _load_complete_embeddings,
    _retrieval_cache_is_current,
    _sha256,
)


class LiveQualityRetrievalContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
