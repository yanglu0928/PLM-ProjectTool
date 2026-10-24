from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_install_root_preflight import validate_install_root  # noqa: E402


class InstallRootPreflightTests(unittest.TestCase):
    def test_ascii_install_roots(self) -> None:
        self.assertEqual(validate_install_root("C:\\PLMTool"), "C:\\PLMTool")
        self.assertEqual(validate_install_root("D:\\Apps\\PLM Tool"), "D:\\Apps\\PLM Tool")

    def test_non_ascii_and_unsafe_roots_fail_closed(self) -> None:
        values = ("D:\\AI工具\\PLMTool", "C:\\", "PLMTool", "\\\\server\\share\\PLMTool",
                  "C:/PLMTool", "C:\\PLMTool\\..\\other", "C:\\PLMTool\\.",
                  "C:\\PLMTool\\", "C:\\CON", "C:\\PLMTool\\bad?name",
                  "C:\\PLMTool\n")
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_install_root(value)


if __name__ == "__main__":
    unittest.main()
