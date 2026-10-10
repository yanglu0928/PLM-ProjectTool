"""Assemble a new NON-RELEASE Windows unified + PG18 ZIP from pinned inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import _verify_archive, digest_path
from package_windows_unified_candidate import _copy_stream, zip_members
from plan_windows_unified_pg18_composition import PG_SHA256, UNIFIED_SHA256, plan


PLAN_SHA256 = "6741b716c886f9128bf6c2bca6a60ff2f83ae3c07eefa82d521d6ee2348761ef"
KIND = "WINDOWS11_UNIFIED_PG18_DEVELOPMENT_CANDIDATE"


def make_manifest(unified_manifest: dict, pg_manifest: dict, count: int) -> dict:
    if (unified_manifest.get("kind") != "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE"
            or pg_manifest.get("kind") != "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE"
            or unified_manifest.get("release_eligible") is not False
            or pg_manifest.get("release_eligible") is not False):
        raise ValueError("source manifest kind/release flag rejected")
    return {
        "kind": KIND, "release_eligible": False, "installation_performed": False,
        "database_started_by_assembly": False, "payload_file_count": count,
        "source_unified_sha256": UNIFIED_SHA256, "source_pg_sha256": PG_SHA256,
        "source_plan_sha256": PLAN_SHA256, "postgresql_version": "18.6", "pgvector_version": "0.8.6",
        "vendored_python_distributions": 106, "no_jbig_pe_count": 34,
        "ocr_python_notice_file_count": 25, "legal_clearance": False,
        "corresponding_source_included": False,
        "missing_release_components": [
            "product License/public key and verified signing provenance",
            "formal installer, target account ACL, HTTPS and service registration",
            "third-party LICENSE/NOTICE and corresponding-source/legal clearance",
            "real quality, upgrade/backup and Windows Server 2025 product acceptance",
            "Debian 13 release acceptance deferred by user", "Gate 3 through release/UAT",
        ],
    }


def build(unified_path: Path, pg_path: Path, plan_path: Path, output_parent: Path) -> dict:
    if digest_path(plan_path) != PLAN_SHA256 or not output_parent.is_dir():
        raise ValueError("pinned composition plan or output parent missing")
    planned = json.loads(plan_path.read_text(encoding="utf-8"))
    current = plan(unified_path, pg_path)
    if current != planned or current["combined_payload_count"] != 21103:
        raise ValueError("source ZIPs differ from pinned composition plan")
    run_root = output_parent / ("unified-pg18-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    output_path = run_root / "NOT-FOR-RELEASE-windows11-unified-pg18-candidate.zip"
    hashes: dict[str, str] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(unified_path) as unified, zipfile.ZipFile(pg_path) as pg:
        sources = [(unified, 19474), (pg, 1629)]
        inventories = []
        manifests = []
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as output:
            for source, count in sources:
                members = zip_members(source)
                source_hashes = {}
                for line in source.read("payload-sha256sums.txt").decode("ascii").splitlines():
                    digest, name = line.split("  ", 1)
                    source_hashes[name] = digest
                if len(source_hashes) != count:
                    raise ValueError("source payload count changed")
                for name in sorted(source_hashes):
                    if name not in members or name.casefold() in seen:
                        raise ValueError("source payload conflict")
                    with source.open(name) as inp, output.open(name, "w", force_zip64=True) as out:
                        digest = _copy_stream(inp, out)
                    if digest != source_hashes[name]:
                        raise ValueError(f"source payload changed during assembly: {name}")
                    hashes[name] = digest
                    seen.add(name.casefold())
                inventories.append(json.loads(source.read("third-party-inventory.json")))
                manifests.append(json.loads(source.read("manifest.json")))
            sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode("ascii")
            output.writestr("payload-sha256sums.txt", sums)
            inventory = {"schema_version": "plm.combined-third-party-inventory.v1",
                         "review_status": "REVIEW_REQUIRED", "unified": inventories[0],
                         "postgresql_pgvector": inventories[1]}
            inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            output.writestr("third-party-inventory.json", inventory_bytes)
            manifest = make_manifest(manifests[0], manifests[1], len(hashes))
            manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
            output.writestr("manifest.json", manifest_bytes)
    if digest_path(unified_path) != UNIFIED_SHA256 or digest_path(pg_path) != PG_SHA256:
        raise ValueError("source ZIP changed during assembly")
    expected = {**hashes, "payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    _verify_archive(output_path, expected)
    result = {"status": "NON_RELEASE_UNIFIED_PG18_INTEGRITY_PASS", "release_eligible": False,
              "archive": str(output_path), "archive_sha256": digest_path(output_path),
              "archive_bytes": output_path.stat().st_size, "payload_file_count": len(hashes)}
    (run_root / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unified", required=True, type=Path)
    parser.add_argument("--pg", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.unified, args.pg, args.plan, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
