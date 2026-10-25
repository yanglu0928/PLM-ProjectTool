"""Read-only install gate plan for the pinned unified+PG18 NON-RELEASE ZIP.

No extraction, install-root creation, service registration, or migration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_windows_unified_pg18_candidate import KIND, PLAN_SHA256
from plan_windows_unified_pg18_composition import inspect
from windows_install_root_preflight import validate_install_root


CANDIDATE_SHA256 = "c54a7862872d402a6c9763287a508dc63dd602049f93aa6097e5a8e8e0766ef2"
OPEN_GATES = [
    "formal product License/public key and signing provenance",
    "complete third-party NOTICE/corresponding source and legal review",
    "installer, target service account, ACL, HTTPS and three SCM services",
    "migration/backup/restore and controlled restart with target account",
    "real OCR/AI quality, permissions, performance, plugin and UAT",
    "Windows Server 2025 product acceptance",
    "Debian 13 acceptance deferred by user but retained as release target",
    "Gate 3 through Gate 7 evidence",
]


def plan_install(candidate: Path, install_root: str) -> dict:
    root = validate_install_root(install_root)  # No ZIP I/O for an unsafe root.
    manifest, hashes = inspect(candidate, CANDIDATE_SHA256, KIND, 21103)
    required = {
        "installation_performed": False, "database_started_by_assembly": False,
        "legal_clearance": False, "corresponding_source_included": False,
        "source_plan_sha256": PLAN_SHA256, "postgresql_version": "18.6",
        "pgvector_version": "0.8.6", "vendored_python_distributions": 106,
        "no_jbig_pe_count": 34, "ocr_python_notice_file_count": 25,
    }
    if any(manifest.get(key) != expected for key, expected in required.items()):
        raise ValueError("combined candidate gate metadata rejected")
    if not all(any(name.startswith(prefix) for name in hashes) for prefix in (
            "payload/runtime/", "payload/frontend/dist/", "payload/ocr/",
            "payload/pgsql/bin/", "payload/pgsql/lib/", "payload/pgsql/share/",
            "payload/third-party-licenses/")):
        raise ValueError("combined candidate runtime family missing")
    # Inspect already verified the ZIP identity, file set and every payload hash.
    return {
        "status": "NON_RELEASE_READ_ONLY_INSTALL_GATE_PLAN",
        "install_root": root, "install_root_exists": Path(root).exists(),
        "candidate_sha256": CANDIDATE_SHA256, "payload_file_count": len(hashes),
        "source_unified_sha256": manifest["source_unified_sha256"],
        "source_pg_sha256": manifest["source_pg_sha256"],
        "install_authorized": False, "release_eligible": False,
        "archive_extracted": False, "services_changed": False, "migration_executed": False,
        "open_gates": OPEN_GATES,
        "next_safe_action": "stage the exact ZIP only in a new ASCII Temp child and verify all bytes",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args()
    print(json.dumps(plan_install(args.candidate, args.install_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
