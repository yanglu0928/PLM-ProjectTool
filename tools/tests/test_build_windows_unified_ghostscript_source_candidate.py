from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_ghostscript_source_candidate import build, updated_metadata  # noqa: E402


class GhostscriptSourceCandidateTests(unittest.TestCase):
    def test_metadata_keeps_formal_release_gate_closed(self) -> None:
        manifest = {"payload_file_count": 21112, "release_eligible": False,
                    "legal_clearance": False, "installation_performed": False}
        inventory = {"review_status": "REVIEW_REQUIRED"}
        raw_manifest, raw_inventory = updated_metadata(manifest, inventory, 21114)
        self.assertIn(b'"payload_file_count": 21114', raw_manifest)
        self.assertIn(b'"release_eligible": false', raw_manifest)
        self.assertIn(b'"review_status": "REVIEW_REQUIRED"', raw_inventory)
        self.assertIn(b'"reproducible_windows_binary_build_verified": false', raw_inventory)

    def test_legal_or_release_metadata_change_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "boundary changed"):
            updated_metadata({"payload_file_count": 21112, "release_eligible": True,
                              "legal_clearance": False},
                             {"review_status": "REVIEW_REQUIRED"}, 21114)

    def test_bad_parent_rejected_before_source(self) -> None:
        with patch("build_windows_unified_ghostscript_source_candidate.verify",
                   side_effect=ValueError("bad parent")):
            with patch("build_windows_unified_ghostscript_source_candidate.audit_source") as source:
                with self.assertRaisesRegex(ValueError, "bad parent"):
                    build(Path("missing.zip"), Path("missing-parent.zip"), Path("missing.tar.xz"), Path("."))
                source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
