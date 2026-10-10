"""Independently verify the fixed P43 Ghostscript-source NON-RELEASE ZIP."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from audit_ghostscript_source_input import SOURCE_SHA256
from build_windows_unified_ghostscript_source_candidate import (
    KIND, LICENSE_MEMBER, LICENSE_SHA256, SOURCE_MEMBER,
)
from plan_windows_unified_pg18_composition import inspect
from verify_windows_unified_caddy_go_source_candidate import (
    ARCHIVE_SHA256 as P33_SHA256, verify as verify_parent,
)
from build_windows_unified_caddy_go_source_candidate import KIND as P33_KIND


ARCHIVE_SHA256 = "764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5"
ARCHIVE_BYTES = 748147289


def check_lineage(manifest: dict, inventory: dict, hashes: dict[str, str],
                  parent_hashes: dict[str, str]) -> None:
    additions = {SOURCE_MEMBER.casefold(): SOURCE_SHA256,
                 LICENSE_MEMBER.casefold(): LICENSE_SHA256}
    if ({name: value for name, value in hashes.items() if name not in parent_hashes} != additions
            or any(hashes.get(name) != value for name, value in parent_hashes.items())
            or len(hashes) != len(parent_hashes) + 2):
        raise ValueError("P43 source candidate payload lineage differs")
    ghost = inventory.get("ghostscript_source", {})
    if (manifest.get("source_p33_sha256") != P33_SHA256
            or manifest.get("ghostscript_source_sha256") != SOURCE_SHA256
            or manifest.get("ghostscript_source_included") is not True
            or any(manifest.get(key) is not False for key in (
                "release_eligible", "legal_clearance", "installation_performed",
                "service_registration_performed", "formal_tls_material_included"))
            or inventory.get("review_status") != "REVIEW_REQUIRED"
            or ghost.get("source_path") != SOURCE_MEMBER
            or ghost.get("source_sha256") != SOURCE_SHA256
            or ghost.get("license_path") != LICENSE_MEMBER
            or ghost.get("license_sha256") != LICENSE_SHA256
            or ghost.get("review_status") != "REVIEW_REQUIRED"
            or ghost.get("legal_clearance") is not False
            or ghost.get("reproducible_windows_binary_build_verified") is not False):
        raise ValueError("P43 source candidate legal or provenance boundary differs")


def verify(candidate: Path, parent: Path, ancestor: Path) -> dict:
    if not candidate.is_file() or candidate.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("P43 source candidate archive size mismatch")
    manifest, hashes = inspect(candidate, ARCHIVE_SHA256, KIND, 21114)
    parent_identity = verify_parent(parent, ancestor)
    _, parent_hashes = inspect(parent, P33_SHA256, P33_KIND, 21112)
    with zipfile.ZipFile(candidate) as archive:
        inventory = json.loads(archive.read("third-party-inventory.json"))
    check_lineage(manifest, inventory, hashes, parent_hashes)
    return {"status": "NON_RELEASE_GHOSTSCRIPT_SOURCE_INDEPENDENT_VERIFY_PASS",
            "release_eligible": False, "legal_clearance": False,
            "archive_sha256": ARCHIVE_SHA256, "archive_bytes": ARCHIVE_BYTES,
            "payload_file_count": len(hashes),
            "parent_p33_sha256": parent_identity["archive_sha256"],
            "unchanged_parent_payload_count": len(parent_hashes),
            "ghostscript_addition_count": 2,
            "installation_performed": False,
            "service_registration_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--ancestor", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate, args.parent, args.ancestor),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
