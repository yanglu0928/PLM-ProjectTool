from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rehearse_windows_unified_caddy_layout import rehearse  # noqa: E402


class CaddyLayoutTests(unittest.TestCase):
    def test_existing_output_rejected_before_source_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as output:
            with patch("rehearse_windows_unified_caddy_layout.plan_install") as plan:
                with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                    rehearse(Path("missing.zip"), Path("missing-stage"), Path(output))
                plan.assert_not_called()

    def test_non_temp_output_rejected(self) -> None:
        with patch("rehearse_windows_unified_caddy_layout.plan_install") as plan:
            with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                rehearse(Path("missing.zip"), Path("missing-stage"), Path("C:/PLMTool"))
            plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
