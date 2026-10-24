from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_caddy_isolated_layout_https import verify_layout  # noqa: E402


class CaddyLayoutHttpsTests(unittest.TestCase):
    def test_non_isolated_roots_rejected_before_candidate_verification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as layout:
            with patch("smoke_caddy_isolated_layout_https.plan_install") as plan:
                with self.assertRaisesRegex(ValueError, "isolated layout/stage"):
                    verify_layout(Path("missing.zip"), Path(layout), Path(layout))
                plan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
