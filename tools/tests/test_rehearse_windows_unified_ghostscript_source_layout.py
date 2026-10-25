from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rehearse_windows_unified_ghostscript_source_layout import rehearse  # noqa: E402


class GhostscriptSourceLayoutTests(unittest.TestCase):
    def test_existing_output_rejected_before_archive_read(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as output:
            with patch("rehearse_windows_unified_ghostscript_source_layout.verify_candidate") as verify:
                with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
                    rehearse(Path("candidate.zip"), Path("parent.zip"), Path("ancestor.zip"),
                             Path("stage"), Path(output))
                verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
