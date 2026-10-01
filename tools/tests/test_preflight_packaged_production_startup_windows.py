from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE, preflight  # noqa: E402


class PackagedStartupPreflightTests(unittest.TestCase):
    def test_public_key_location_matches_embedded_python_packages(self) -> None:
        self.assertEqual(PUBLIC_KEY_RELATIVE,
                         "runtime/python/packages/plm_assistant/modules/license/trust/product_public_key.json")

    def test_unverified_layout_rejected_before_credential_inspection(self) -> None:
        with patch("preflight_packaged_production_startup_windows.verify_layout", side_effect=ValueError("bad layout")):
            with patch("preflight_packaged_production_startup_windows.database_credential_present") as credential:
                with self.assertRaisesRegex(ValueError, "bad layout"):
                    preflight(Path("missing.zip"), Path("stage"), Path("layout"))
                credential.assert_not_called()


if __name__ == "__main__":
    unittest.main()
