from __future__ import annotations

import sys
import unittest
from pathlib import Path


COMPAT_DIR = Path(__file__).parents[1] / "scripts" / "compat"
sys.path.insert(0, str(COMPAT_DIR))

from ocrmypdf_windows_compat import (  # noqa: E402
    decode_tesseract_output,
    parse_tesseract_output,
)


class TesseractOutputCompatibilityTests(unittest.TestCase):
    def test_utf8_output(self) -> None:
        output = "提示：正常\nDeskew angle: 0.0010\n".encode()

        parsed = parse_tesseract_output(output)

        self.assertEqual(parsed["Deskew angle"], "0.0010")

    def test_chinese_windows_output(self) -> None:
        output = "错误路径: D:\\AI工具\\模型\nDeskew angle: -0.0020\n".encode("gb18030")

        decoded = decode_tesseract_output(output)
        parsed = parse_tesseract_output(output)

        self.assertIn("AI工具", decoded)
        self.assertEqual(parsed["Deskew angle"], "-0.0020")


if __name__ == "__main__":
    unittest.main()
