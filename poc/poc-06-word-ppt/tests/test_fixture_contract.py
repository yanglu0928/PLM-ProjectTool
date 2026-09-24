from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

POC_DIR = Path(__file__).resolve().parents[1]
SCRIPT = POC_DIR / "scripts" / "build_word_fixture.py"
SPEC = importlib.util.spec_from_file_location("build_word_fixture", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FixtureContractTests(unittest.TestCase):
    def test_word_page_contract_is_exactly_one_hundred(self) -> None:
        self.assertEqual(100, MODULE.PAGE_COUNT)

    def test_synthetic_image_exists(self) -> None:
        image = POC_DIR / "input" / "plm-collaboration.png"
        self.assertTrue(image.is_file())
        self.assertGreater(image.stat().st_size, 100_000)

    def test_presentation_contract_declares_fifty_slides(self) -> None:
        source = (POC_DIR / "scripts" / "build_presentation_fixture.mjs").read_text(encoding="utf-8")
        self.assertIn("explicitTotalSlideCount: 50", source)
        self.assertIn("slideNumber <= 50", source)


if __name__ == "__main__":
    unittest.main()
