"""Reconcile fixed P22 legal-evidence files; never issue legal clearance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify


REQUIRED = (
    "payload/ocr/ghostscript/doc/COPYING",
    "payload/third-party-licenses/caddy/LICENSE",
    "payload/third-party-licenses/caddy/windows_amd64.sbom",
    "payload/third-party-licenses/caddy/checksums.txt",
    "payload/third-party-sources/caddy/buildable-artifact.tar.gz",
    "payload/third-party-licenses/postgresql/commandlinetools_3rd_party_licenses.txt",
    "payload/third-party-licenses/pgvector/LICENSE",
    "payload/pgsql/server_license.txt",
)


def classify(names: set[str], inventory: dict) -> dict:
    if set(REQUIRED) - names or inventory.get("review_status") != "REVIEW_REQUIRED":
        raise ValueError("fixed release evidence or review state missing")
    base = inventory.get("base", {})
    if (base.get("review_status") != "REVIEW_REQUIRED"
            or base.get("postgresql_pgvector", {}).get("legal_review_status") != "REVIEW_REQUIRED"
            or base.get("unified", {}).get("frontend_bundled_dependency_review") != "REVIEW_REQUIRED"
            or inventory.get("caddy", {}).get("downstream_notice_review_complete") is not False):
        raise ValueError("nested legal review state changed")
    notices = sorted(name for name in names if name.startswith(
        "payload/third-party-licenses/ocr-python-notices/"))
    sources = sorted(name for name in names if name.startswith("payload/third-party-sources/"))
    if len(notices) != 25 or sources != ["payload/third-party-sources/caddy/buildable-artifact.tar.gz"]:
        raise ValueError("notice/source coverage differs from fixed candidate")
    product_files = sorted(names & {"LICENSE", "NOTICE", "payload/LICENSE", "payload/NOTICE"})
    if product_files:
        raise ValueError("product legal files changed; perform new review")
    return {"status": "NON_RELEASE_EVIDENCE_GAPS_RECONCILED",
            "release_eligible": False, "ocr_python_standalone_notice_files": len(notices),
            "third_party_source_files": len(sources),
            "only_source_family": "caddy", "product_license_notice_files": len(product_files),
            "caddy_downstream_notice_review_complete": False,
            "postgresql_pgvector_legal_review_complete": False,
            "frontend_dependency_review_complete": False,
            "ghostscript_copying_present": True,
            "ghostscript_corresponding_source_in_candidate": False,
            "native_34_pe_release_obligation_review_complete": False,
            "legal_clearance": False}


def audit(candidate: Path) -> dict:
    identity = verify(candidate)
    with zipfile.ZipFile(candidate) as archive:
        names = set(archive.namelist())
        inventory = json.loads(archive.read("third-party-inventory.json"))
        result = classify(names, inventory)
        evidence = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in REQUIRED}
    return {**result, "candidate_sha256": ARCHIVE_SHA256,
            "payload_file_count": identity["payload_file_count"],
            "required_evidence_sha256": evidence,
            "next_review": [
                "qualified legal review of product LICENSE/NOTICE and Ghostscript AGPL distribution obligations",
                "verify corresponding sources/attribution for OCR native 34 PE and 106 Python distributions",
                "review Caddy SBOM 149 components and downstream NOTICE/source obligations",
                "review frontend dependencies, PostgreSQL/pgvector, models and all combined notices",
            ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
