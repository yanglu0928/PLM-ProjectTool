from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ghostscript_source_input import SOURCE_SHA256  # noqa: E402
from build_windows_unified_ghostscript_source_candidate import (  # noqa: E402
    LICENSE_MEMBER, LICENSE_SHA256, SOURCE_MEMBER,
)
from verify_windows_unified_ghostscript_source_candidate import (  # noqa: E402
    P33_SHA256, check_lineage,
)


class GhostscriptSourceCandidateVerifyTests(unittest.TestCase):
    def _fixture(self) -> tuple[dict, dict, dict, dict]:
        manifest = {"source_p33_sha256": P33_SHA256,
                    "ghostscript_source_sha256": SOURCE_SHA256,
                    "ghostscript_source_included": True,
                    "release_eligible": False, "legal_clearance": False,
                    "installation_performed": False,
                    "service_registration_performed": False,
                    "formal_tls_material_included": False}
        inventory = {"review_status": "REVIEW_REQUIRED", "ghostscript_source": {
            "source_path": SOURCE_MEMBER, "source_sha256": SOURCE_SHA256,
            "license_path": LICENSE_MEMBER, "license_sha256": LICENSE_SHA256,
            "review_status": "REVIEW_REQUIRED", "legal_clearance": False,
            "reproducible_windows_binary_build_verified": False}}
        parent = {"payload/old".casefold(): "a" * 64}
        candidate = {**parent, SOURCE_MEMBER.casefold(): SOURCE_SHA256,
                     LICENSE_MEMBER.casefold(): LICENSE_SHA256}
        return manifest, inventory, candidate, parent

    def test_two_additions_and_nonrelease_metadata_accepted(self) -> None:
        check_lineage(*self._fixture())

    def test_changed_parent_payload_rejected(self) -> None:
        manifest, inventory, hashes, parent = self._fixture()
        hashes["payload/old"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            check_lineage(manifest, inventory, hashes, parent)

    def test_false_legal_clearance_rejected(self) -> None:
        manifest, inventory, hashes, parent = self._fixture()
        manifest["legal_clearance"] = True
        with self.assertRaisesRegex(ValueError, "boundary differs"):
            check_lineage(manifest, inventory, hashes, parent)


if __name__ == "__main__":
    unittest.main()
