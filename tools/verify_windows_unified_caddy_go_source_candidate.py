"""Independent fixed-hash verifier for P33 NON-RELEASE Windows candidate."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from audit_go_stdlib_source_input import GO_LICENSE_SHA256, GO_SOURCE_SHA256
from build_windows_unified_caddy_go_source_candidate import (
    GO_LICENSE_MEMBER, GO_SOURCE_MEMBER, KIND,
)
from plan_windows_unified_pg18_composition import inspect
from verify_windows_unified_caddy_candidate import (
    ARCHIVE_SHA256 as SOURCE_SHA256, verify as verify_source,
)


ARCHIVE_SHA256 = "85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc"
ARCHIVE_BYTES = 675167309


def verify(candidate: Path, source: Path) -> dict:
    if not candidate.is_file() or candidate.stat().st_size != ARCHIVE_BYTES:
        raise ValueError("P33 archive size mismatch")
    manifest, hashes = inspect(candidate, ARCHIVE_SHA256, KIND, 21112)
    parent = verify_source(source)
    _, parent_hashes = inspect(source, SOURCE_SHA256,
                               "WINDOWS11_UNIFIED_PG18_CADDY_DEVELOPMENT_CANDIDATE", 21110)
    additions = {GO_SOURCE_MEMBER.casefold(): GO_SOURCE_SHA256,
                 GO_LICENSE_MEMBER.casefold(): GO_LICENSE_SHA256}
    if ({name: value for name, value in hashes.items() if name not in parent_hashes} != additions
            or any(hashes.get(name) != value for name, value in parent_hashes.items())
            or len(hashes) != len(parent_hashes) + 2):
        raise ValueError("P33 payload lineage or added Go evidence differs")
    if (manifest.get("source_p22_sha256") != SOURCE_SHA256
            or manifest.get("go_stdlib_source_sha256") != GO_SOURCE_SHA256
            or manifest.get("go_stdlib_source_included") is not True
            or any(manifest.get(key) is not False for key in (
                "release_eligible", "legal_clearance", "installation_performed",
                "service_registration_performed", "formal_tls_material_included"))):
        raise ValueError("P33 manifest release boundary differs")
    with zipfile.ZipFile(candidate) as archive:
        inventory = json.loads(archive.read("third-party-inventory.json"))
        go = inventory.get("go_stdlib_source", {})
        if (inventory.get("review_status") != "REVIEW_REQUIRED"
                or go.get("review_status") != "REVIEW_REQUIRED"
                or go.get("legal_clearance") is not False
                or go.get("source_path") != GO_SOURCE_MEMBER
                or go.get("source_sha256") != GO_SOURCE_SHA256
                or go.get("license_path") != GO_LICENSE_MEMBER
                or go.get("license_sha256") != GO_LICENSE_SHA256
                or inventory.get("caddy", {}).get("downstream_notice_review_complete") is not False):
            raise ValueError("P33 inventory review boundary differs")
    return {"status": "NON_RELEASE_CADDY_GO_SOURCE_INDEPENDENT_VERIFY_PASS",
            "release_eligible": False, "legal_clearance": False,
            "archive_sha256": ARCHIVE_SHA256, "archive_bytes": ARCHIVE_BYTES,
            "payload_file_count": len(hashes),
            "source_p22_sha256": parent["archive_sha256"],
            "unchanged_parent_payload_count": len(parent_hashes),
            "go_addition_count": len(additions),
            "installation_performed": False, "service_registration_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.candidate, args.source), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
