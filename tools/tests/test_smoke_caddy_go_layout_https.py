from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_caddy_go_layout_https import verify_layout  # noqa: E402


class CaddyGoHttpsTests(unittest.TestCase):
    def test_same_or_non_temp_root_rejected_before_archive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as layout:
            with patch("smoke_caddy_go_layout_https.verify_candidate") as candidate:
                with self.assertRaisesRegex(ValueError, "isolated layout/stage"):
                    verify_layout(Path("new.zip"), Path("old.zip"), Path(layout), Path(layout))
                candidate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
