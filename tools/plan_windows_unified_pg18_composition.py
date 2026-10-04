"""Read-only collision/integrity plan for two pinned NON-RELEASE Windows ZIPs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import digest_path
from package_windows_unified_candidate import safe_name, zip_members
from package_windows_pg18_candidate import KIND as PG_KIND


UNIFIED_SHA256 = "e4fdbcb601f526fd147b73b3e510e82653d85841503b5589dbf5c5d7c2f2eb50"
PG_SHA256 = "d0e038b43240369f7cd66396c34cd8e56d5a7a5a51ae3bc6f5fc41783baa7fd9"
META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}


def inspect(path: Path, expected_sha256: str, expected_kind: str, expected_count: int) -> tuple[dict, dict[str, str]]:
    if digest_path(path) != expected_sha256:
        raise ValueError("composition source ZIP identity mismatch")
    with zipfile.ZipFile(path) as archive:
        members = zip_members(archive)
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != expected_kind or manifest.get("release_eligible") is not False
                or manifest.get("payload_file_count") != expected_count):
            raise ValueError("composition source manifest rejected")
        inventory = json.loads(archive.read("third-party-inventory.json"))
        if not isinstance(inventory, dict) or not META <= set(members):
            raise ValueError("composition source inventory rejected")
        hashes: dict[str, str] = {}
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, sep, name = line.partition("  ")
            safe_name(name)
            if (sep != "  " or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
                    or not name.startswith("payload/") or name.casefold() in hashes):
                raise ValueError("composition source hash manifest rejected")
            hashes[name.casefold()] = digest
        if len(hashes) != expected_count or {name.casefold() for name in members} != set(hashes) | META:
            raise ValueError("composition source file set rejected")
        for name in members:
            if name in META:
                continue
            actual = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    actual.update(block)
            if actual.hexdigest() != hashes[name.casefold()]:
                raise ValueError(f"composition source payload changed: {name}")
    return manifest, hashes


def plan(unified: Path, pg: Path) -> dict:
    unified_manifest, unified_hashes = inspect(unified, UNIFIED_SHA256,
                                                "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE", 19474)
    pg_manifest, pg_hashes = inspect(pg, PG_SHA256, PG_KIND, 1629)
    conflicts = sorted(set(unified_hashes) & set(pg_hashes))
    if conflicts:
        raise ValueError(f"composition payload path conflict: {len(conflicts)}")
    if not all(name.startswith("payload/pgsql/") or name.startswith("payload/third-party-licenses/")
               for name in pg_hashes):
        raise ValueError("PG sidecar target path outside approved prefixes")
    if any(name.startswith("payload/pgsql/") for name in unified_hashes):
        raise ValueError("unified candidate already contains PostgreSQL runtime")
    return {
        "schema_version": "plm.windows-unified-pg18-composition-plan.v1",
        "status": "NON_RELEASE_INPUTS_DISJOINT_AND_VERIFIED",
        "release_eligible": False, "installation_authorized": False,
        "unified_sha256": UNIFIED_SHA256, "pg_sidecar_sha256": PG_SHA256,
        "unified_kind": unified_manifest["kind"], "pg_kind": pg_manifest["kind"],
        "unified_payload_count": len(unified_hashes), "pg_payload_count": len(pg_hashes),
        "combined_payload_count": len(unified_hashes) + len(pg_hashes),
        "case_insensitive_path_conflicts": 0,
        "proposed_layout": "single payload tree; PostgreSQL under payload/pgsql, licenses under payload/third-party-licenses",
        "combined_zip_built": False,
        "open_gates": ["all-source and third-party legal clearance", "product License and public-key provisioning",
                       "formal installer/service-account/ACL/HTTPS", "Windows Server 2025 product acceptance",
                       "Debian 13 acceptance deferred by user", "Gate 3 through release/UAT"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unified", required=True, type=Path)
    parser.add_argument("--pg", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; preserve historical plan")
    result = plan(args.unified, args.pg)
    args.output.write_bytes((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"status": result["status"], "combined_payload_count": result["combined_payload_count"],
                      "output_sha256": digest_path(args.output), "release_eligible": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
