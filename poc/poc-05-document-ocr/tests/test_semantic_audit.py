from __future__ import annotations

import sys
import unittest
from pathlib import Path

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src" / "poc05_parser"))

from semantic_audit import (  # noqa: E402
    best_window_similarity,
    normalize_text,
    reconstruct_page_text,
)


class SemanticAuditTests(unittest.TestCase):
    def test_normalizes_width_case_and_punctuation(self) -> None:
        self.assertEqual("plm项目v90", normalize_text("ＰＬＭ 项目，V9.0"))

    def test_reconstructs_positioned_lines(self) -> None:
        blocks = [
            {"text": "项目", "page": 2, "metadata": {"bbox": [10, 20, 20, 10]}},
            {"text": "验收", "page": 2, "metadata": {"bbox": [40, 21, 20, 10]}},
            {"text": "标准", "page": 2, "metadata": {"bbox": [10, 50, 20, 10]}},
        ]
        self.assertEqual("项目 验收\n标准", reconstruct_page_text(blocks, 2))

    def test_allows_one_character_ocr_error(self) -> None:
        score = best_window_similarity("项目验收标准流程", "项目验改标准流程")
        self.assertGreaterEqual(score, 0.85)


if __name__ == "__main__":
    unittest.main()
