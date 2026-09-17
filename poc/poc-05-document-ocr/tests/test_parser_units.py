from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc05_parser import parse_document  # noqa: E402
from poc05_parser.parser import _paragraph_style_name, _tesseract_image_data  # noqa: E402


class ParserUnitTests(unittest.TestCase):
    def test_tesseract_image_handle_is_closed(self) -> None:
        fake_pytesseract = ModuleType("pytesseract")
        fake_pytesseract.Output = SimpleNamespace(DICT="DICT")
        fake_pytesseract.pytesseract = SimpleNamespace(tesseract_cmd=None)
        fake_pytesseract.image_to_data = MagicMock(return_value={"text": [], "conf": []})
        image_context = MagicMock()
        page_image = object()
        image_context.__enter__.return_value = page_image

        with (
            patch.dict(sys.modules, {"pytesseract": fake_pytesseract}),
            patch("poc05_parser.parser.Image.open", return_value=image_context),
        ):
            result = _tesseract_image_data(Path("page.png"))

        self.assertEqual({"text": [], "conf": []}, result)
        fake_pytesseract.image_to_data.assert_called_once_with(
            page_image, lang="chi_sim+eng", output_type="DICT"
        )
        image_context.__exit__.assert_called_once()

    def test_csv_preserves_row_source(self) -> None:
        parsed = parse_document(POC_DIR / "input" / "sample.csv").to_dict()
        self.assertEqual(parsed["schema_version"], "poc-05.1")
        self.assertIsNone(parsed["pages"][0]["number"])
        self.assertEqual(parsed["blocks"][0]["source_locator"], "csv/rows/1")
        self.assertEqual(parsed["blocks"][1]["table"]["row"], 2)

    def test_unsupported_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="poc05-unit-") as temp_dir:
            unknown = Path(temp_dir) / "sample.txt"
            unknown.write_text("sample", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported document type"):
                parse_document(unknown)

    def test_docx_paragraph_style_without_name_is_treated_as_empty(self) -> None:
        paragraph = SimpleNamespace(style=SimpleNamespace(name=None))
        self.assertEqual(_paragraph_style_name(paragraph), "")


if __name__ == "__main__":
    unittest.main()
