from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rehearse_windows_unified_pg18_layout import target_name, validate_output_root  # noqa: E402


class UnifiedPg18LayoutTests(unittest.TestCase):
    def test_explicit_model_and_runtime_mapping(self) -> None:
        self.assertEqual(target_name("payload/ocr/models/PP-OCRv5_mobile_det/config.json"),
                         "app/models/PP-OCRv5_mobile_det/config.json")
        self.assertEqual(target_name("payload/pgsql/bin/postgres.exe"), "runtime/pgsql/bin/postgres.exe")
        self.assertEqual(target_name("payload/runtime/python.exe"), "runtime/python/python.exe")
        self.assertEqual(target_name("payload/frontend/dist/index.html"), "app/frontend/dist/index.html")
        with self.assertRaisesRegex(ValueError, "unmapped"):
            target_name("payload/private/key.txt")

    def test_output_must_be_new_ascii_temp_child(self) -> None:
        temp = Path(tempfile.gettempdir())
        fresh = temp / "plm-install-rehearsal-12345678"
        self.assertEqual(validate_output_root(fresh), fresh)
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as existing:
            with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                validate_output_root(Path(existing))
        with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
            validate_output_root(temp / "nested" / "plm-install-rehearsal-12345678")


if __name__ == "__main__":
    unittest.main()
