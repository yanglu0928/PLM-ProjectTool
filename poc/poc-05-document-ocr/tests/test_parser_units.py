from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc05_parser import parse_document  # noqa: E402
from poc05_parser.parser import (  # noqa: E402
    _paragraph_style_name,
    _tesseract_image_data,
    _write_docx_without_null_relationships,
)


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

    def test_docx_null_internal_relationship_is_removed_from_temporary_copy(self) -> None:
        relationships = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="image" Target="NULL"/>
          <Relationship Id="rId2" Type="styles" Target="styles.xml"/>
          <Relationship Id="rId3" Type="link" Target="https://example.invalid" TargetMode="External"/>
        </Relationships>"""
        with tempfile.TemporaryDirectory(prefix="poc05-null-rel-") as temp_dir:
            source = Path(temp_dir) / "source.docx"
            target = Path(temp_dir) / "target.docx"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word/_rels/document.xml.rels", relationships)
                archive.writestr("word/document.xml", "document")

            removed = _write_docx_without_null_relationships(source, target)

            self.assertEqual(1, removed)
            with zipfile.ZipFile(target) as archive:
                root = ElementTree.fromstring(
                    archive.read("word/_rels/document.xml.rels")
                )
                targets = [item.attrib.get("Target") for item in root]
                self.assertEqual(["styles.xml", "https://example.invalid"], targets)


if __name__ == "__main__":
    unittest.main()
