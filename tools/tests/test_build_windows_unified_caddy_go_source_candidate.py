from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_caddy_go_source_candidate import (
    GO_LICENSE_MEMBER, GO_SOURCE_MEMBER, KIND, build, updated_metadata,
)  # noqa: E402


class CaddyGoSourceCandidateTests(unittest.TestCase):
    def test_metadata_preserves_non_release_and_lineage(self) -> None:
        manifest = {"release_eligible": False, "legal_clearance": False,
                    "payload_file_count": 21110, "kind": "old"}
        inventory = {"review_status": "REVIEW_REQUIRED", "caddy": {"version": "2.11.4"}}
        new_manifest, new_inventory = updated_metadata(manifest, inventory, 21112)
        parsed_manifest, parsed_inventory = json.loads(new_manifest), json.loads(new_inventory)
        self.assertEqual(parsed_manifest["kind"], KIND)
        self.assertFalse(parsed_manifest["release_eligible"])
        self.assertEqual(parsed_manifest["payload_file_count"], 21112)
        self.assertEqual(parsed_inventory["go_stdlib_source"]["source_path"], GO_SOURCE_MEMBER)
        self.assertEqual(parsed_inventory["go_stdlib_source"]["license_path"], GO_LICENSE_MEMBER)
        self.assertFalse(parsed_inventory["go_stdlib_source"]["legal_clearance"])

    def test_unverified_source_rejected_before_output(self) -> None:
        with patch("build_windows_unified_caddy_go_source_candidate.verify_source", side_effect=ValueError("bad P22")):
            with self.assertRaisesRegex(ValueError, "bad P22"):
                build(Path("bad.zip"), Path("go.tar.gz"), Path.cwd())


if __name__ == "__main__":
    unittest.main()
