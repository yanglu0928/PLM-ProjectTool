from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_pg18_candidate import KIND, make_manifest  # noqa: E402
from verify_windows_unified_extract import ALLOWED_KINDS  # noqa: E402


class UnifiedPg18BuilderTests(unittest.TestCase):
    def test_combined_manifest_preserves_non_release_boundary(self) -> None:
        unified = {"kind": "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE", "release_eligible": False}
        pg = {"kind": "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE", "release_eligible": False}
        manifest = make_manifest(unified, pg, 21103)
        self.assertEqual(manifest["kind"], KIND)
        self.assertFalse(manifest["release_eligible"])
        self.assertFalse(manifest["legal_clearance"])
        self.assertEqual(manifest["payload_file_count"], 21103)
        self.assertIn(KIND, ALLOWED_KINDS)

    def test_release_source_rejected(self) -> None:
        unified = {"kind": "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE", "release_eligible": True}
        pg = {"kind": "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE", "release_eligible": False}
        with self.assertRaisesRegex(ValueError, "source manifest"):
            make_manifest(unified, pg, 1)


if __name__ == "__main__":
    unittest.main()
