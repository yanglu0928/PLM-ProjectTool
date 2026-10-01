"""Reconcile fixed P43 third-party evidence without issuing legal clearance."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import digest_path
from package_windows_unified_candidate import NO_JBIG_CSV_SHA256
from verify_windows_unified_ghostscript_source_candidate import (
    ARCHIVE_SHA256, verify,
)


SOURCES = {
    "payload/third-party-sources/caddy/buildable-artifact.tar.gz",
    "payload/third-party-sources/go/go1.26.3.src.tar.gz",
    "payload/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz",
}
REQUIRED = SOURCES | {
    "payload/ocr/ghostscript/doc/COPYING",
    "payload/third-party-licenses/ghostscript/source-LICENSE",
    "payload/third-party-licenses/go/LICENSE",
    "payload/third-party-licenses/caddy/LICENSE",
    "payload/third-party-licenses/caddy/windows_amd64.sbom",
    "payload/third-party-licenses/caddy/checksums.txt",
    "payload/third-party-licenses/pgvector/LICENSE",
    "payload/third-party-licenses/postgresql/commandlinetools_3rd_party_licenses.txt",
    "payload/pgsql/server_license.txt",
    "payload/runtime/LICENSE.txt",
}
PRODUCT_FILES = {"LICENSE", "NOTICE", "payload/LICENSE", "payload/NOTICE"}


def classify(names: set[str], inventory: dict, native_rows: list[dict]) -> dict:
    if REQUIRED - names or {name for name in names if name.startswith(
            "payload/third-party-sources/")} != SOURCES:
        raise ValueError("P43 release evidence path set differs")
    if PRODUCT_FILES & names:
        raise ValueError("product legal files changed; new qualified review required")
    license_files = {name for name in names if name.startswith("payload/third-party-licenses/")}
    standalone = [name for name in license_files if name.startswith(
        "payload/third-party-licenses/notices/")]
    ocr_python = [name for name in license_files if name.startswith(
        "payload/third-party-licenses/ocr-python-notices/")]
    frontend = [name for name in license_files if name.startswith(
        "payload/third-party-licenses/frontend/")]
    base = inventory.get("base", {})
    unified = base.get("unified", {})
    postgres = base.get("postgresql_pgvector", {})
    caddy = inventory.get("caddy", {})
    ghostscript = inventory.get("ghostscript_source", {})
    if (len(license_files) != 190 or len(standalone) != 152
            or len(ocr_python) != 25 or len(frontend) != 6
            or unified.get("distribution_count") != 106
            or unified.get("frontend_bundled_dependency_review") != "REVIEW_REQUIRED"
            or postgres.get("legal_review_status") != "REVIEW_REQUIRED"
            or caddy.get("sbom_component_count") != 149
            or caddy.get("downstream_notice_review_complete") is not False
            or ghostscript.get("review_status") != "REVIEW_REQUIRED"
            or ghostscript.get("legal_clearance") is not False
            or inventory.get("review_status") != "REVIEW_REQUIRED"
            or len(native_rows) != 34
            or any(row.get("release_obligations_reviewed") != "NO" for row in native_rows)):
        raise ValueError("P43 legal review state differs")
    return {"status": "GHOSTSCRIPT_SOURCE_ADDED_LEGAL_REVIEW_OPEN",
            "release_eligible": False, "legal_clearance": False,
            "product_license_notice_files": 0,
            "third_party_evidence_sidecar_files": len(license_files),
            "third_party_source_archives": len(SOURCES),
            "python_distributions": 106,
            "python_historical_standalone_notices": len(standalone),
            "python_ocr_standalone_notices": len(ocr_python),
            "frontend_license_sidecars": len(frontend),
            "frontend_review": "REVIEW_REQUIRED",
            "caddy_sbom_components": 149,
            "caddy_downstream_review_complete": False,
            "postgresql_pgvector_review": "REVIEW_REQUIRED",
            "native_pe_review_required": len(native_rows),
            "ghostscript_source_bundled": True,
            "ghostscript_legal_review": "REVIEW_REQUIRED",
            "next_review": [
                "qualified review of product license and combined-work distribution approach",
                "component-by-component NOTICE and source obligations for 34 native PE and 106 Python distributions",
                "frontend and Caddy downstream notice/source review",
                "PostgreSQL, pgvector, models and Ghostscript bundled third-party terms review",
                "independent legal clearance before external release",
            ]}


def audit(candidate: Path, parent: Path, ancestor: Path, native_matrix: Path) -> dict:
    identity = verify(candidate, parent, ancestor)
    if digest_path(native_matrix) != NO_JBIG_CSV_SHA256:
        raise ValueError("native PE review matrix identity differs")
    with native_matrix.open("r", encoding="utf-8", newline="") as stream:
        native_rows = list(csv.DictReader(stream))
    with zipfile.ZipFile(candidate) as archive:
        names = set(archive.namelist())
        inventory = json.loads(archive.read("third-party-inventory.json"))
    return {**classify(names, inventory, native_rows),
            "candidate_sha256": ARCHIVE_SHA256,
            "payload_file_count": identity["payload_file_count"],
            "native_matrix_sha256": NO_JBIG_CSV_SHA256}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--ancestor", type=Path, required=True)
    parser.add_argument("--native-matrix", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.ancestor,
                           args.native_matrix), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
