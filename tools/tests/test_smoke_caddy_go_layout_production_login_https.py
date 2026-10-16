from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_caddy_go_layout_production_login_https import smoke  # noqa: E402


class CaddyGoLoginTests(unittest.TestCase):
    def test_unverified_layout_never_starts_login(self) -> None:
        with patch("smoke_caddy_go_layout_production_login_https.verify_layout", side_effect=ValueError("bad layout")):
            with patch("smoke_caddy_go_layout_production_login_https.original_smoke") as login:
                with self.assertRaisesRegex(ValueError, "bad layout"):
                    smoke(Path("candidate.zip"), Path("source.zip"), Path("stage"), Path("layout"))
                login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
