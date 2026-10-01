from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preflight_packaged_production_startup_windows import preflight  # noqa: E402


class PackagedStartupPreflightTests(unittest.TestCase):
    def test_unverified_layout_rejected_before_credential_inspection(self) -> None:
        with patch("preflight_packaged_production_startup_windows.verify_layout", side_effect=ValueError("bad layout")):
            with patch("preflight_packaged_production_startup_windows.database_credential_present") as credential:
                with self.assertRaisesRegex(ValueError, "bad layout"):
                    preflight(Path("missing.zip"), Path("stage"), Path("layout"))
                credential.assert_not_called()


if __name__ == "__main__":
    unittest.main()
