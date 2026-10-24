"""Audit pinned PostgreSQL 18.6/pgvector 0.8.6 offline Windows inputs.

Read-only: never starts a server, runs initdb, installs, or touches a database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from package_windows_embedded_candidate import digest_path


PGVECTOR_COMMIT = "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
ASSETS = {
    "postgresql-18.6-1-windows-x64.exe": (375833688, "cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1"),
    "postgresql-18.6-1-windows-x64-binaries.zip": (343808005, "fbe23da234ee31547bf8a36d29dfd81e82b849df2d2b78d2eecb43d360252f8c"),
    "pgvector-0.8.6.zip": (214357, "250f5f488a5e512c8781c338608dfac32ae34f97088970a1b5bb8f5be797caf8"),
    "vs_BuildTools-17.14.41.exe": (4473792, "37bb0fb429d163ecebd272a865d11a37b906d152bef960da2ddb29c2e2fd6eeb"),
}
BUNDLE_SHA256 = "79acfd9c050676189b3030ede5b63353f6ec2922c9989c4655519c4e80ade03f"
RUNTIME_ARCHIVE_SHA256 = "67869cf66d6395cf9395b5ac2b640a5af00d6980911dacbfcead409f5f5f3d0d"
RUNTIME_FILES = {
    "lib/vector.dll": "e070cdd11882ddc2560d0ae242aab323b49f5f876481345c3bece9fe5bba2fd4",
    "share/extension/vector.control": "a54161fa561100fdc4ad31adec51f2841ca9d05496f1ddca818df87c58709cbe",
    "share/extension/vector--0.8.6.sql": "1e4d2de57f0a16c5c2b259d77655aecf9c740713beae4ac4b511549fceb6aafb",
    "server_license.txt": "39294f3f5b41533b307e118ee37c356f32cbc7746fc97e8b91f1b49a9068a24e",
}
PGVECTOR_LICENSE_SHA256 = "8e9a3fcc1aae0eba1d07bf8eb27de9a055baecdf1a31390cf6f2af1ab73c1802"


def verify_assets(downloads: Path) -> list[dict]:
    result = []
    for name, (size, expected) in ASSETS.items():
        path = downloads / name
        if not path.is_file() or path.stat().st_size != size or digest_path(path) != expected:
            raise ValueError(f"offline asset identity mismatch: {name}")
        result.append({"name": name, "size_bytes": size, "sha256": expected})
    return result


def _hash_stream(source) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def audit(downloads: Path, pg_root: Path, source_root: Path, bundle: Path) -> dict:
    assets = verify_assets(downloads)
    version = subprocess.run([str(pg_root / "bin/pg_config.exe"), "--version"],
                             capture_output=True, text=True, timeout=15, check=False)
    if version.returncode != 0 or version.stdout.strip() != "PostgreSQL 18.6":
        raise ValueError("local PostgreSQL binary version mismatch")
    runtime = []
    for name, expected in RUNTIME_FILES.items():
        path = pg_root / name
        if not path.is_file() or digest_path(path) != expected:
            raise ValueError(f"local runtime input changed: {name}")
        runtime.append({"path": name, "sha256": expected, "size_bytes": path.stat().st_size})
    if "default_version = '0.8.6'" not in (pg_root / "share/extension/vector.control").read_text(encoding="utf-8"):
        raise ValueError("pgvector control version mismatch")
    commit = subprocess.run(["git", "-C", str(source_root), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=15, check=False)
    if commit.returncode != 0 or commit.stdout.strip() != PGVECTOR_COMMIT:
        raise ValueError("pgvector source commit mismatch")
    license_file = source_root / "LICENSE"
    if digest_path(license_file) != PGVECTOR_LICENSE_SHA256:
        raise ValueError("pgvector source license text changed")
    if digest_path(bundle) != BUNDLE_SHA256:
        raise ValueError("historical PoC bundle hash mismatch")
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("postgresql_version") != "18.6"
                or manifest.get("pgvector_version") != "0.8.6"
                or manifest.get("pgvector_source_commit") != PGVECTOR_COMMIT
                or manifest.get("runtime_archive", {}).get("sha256") != RUNTIME_ARCHIVE_SHA256):
            raise ValueError("historical PoC bundle manifest mismatch")
        inner_name = manifest["runtime_archive"]["name"]
        with archive.open(inner_name) as inner:
            if _hash_stream(inner) != RUNTIME_ARCHIVE_SHA256:
                raise ValueError("historical PoC runtime archive mismatch")
        cache_paths = [name for name in archive.namelist() if "__pycache__/" in name or name.endswith(".pyc")]
        if not cache_paths:
            raise ValueError("historical PoC bundle cache evidence changed")
    return {
        "schema_version": "plm.postgresql18-pgvector-windows-inputs.v1",
        "status": "OFFLINE_INPUT_BYTES_VERIFIED_NOT_RELEASE_READY",
        "release_eligible": False,
        "platform": "Windows x86-64",
        "postgresql_version": "18.6",
        "pgvector_version": "0.8.6",
        "pgvector_source_commit": PGVECTOR_COMMIT,
        "offline_assets": assets,
        "local_runtime_evidence": runtime,
        "pgvector_source_license_sha256": PGVECTOR_LICENSE_SHA256,
        "historical_poc_bundle_sha256": BUNDLE_SHA256,
        "historical_runtime_archive_sha256": RUNTIME_ARCHIVE_SHA256,
        "historical_poc_bundle_cache_file_count": len(cache_paths),
        "historical_poc_bundle_release_reusable": False,
        "formal_installer_verified": False,
        "fresh_offline_install_in_this_audit": False,
        "known_gaps": [
            "PoC bundle contains test code/cache and is not a customer release package",
            "prepare minimal exact runtime with third-party notices and source provenance",
            "supply formal installer/ACL/service account/config and backup/upgrade workflow",
            "verify Windows 11 and Windows Server 2025 release account end-to-end",
            "Debian 13 verification deferred by user but remains a target",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", required=True, type=Path)
    parser.add_argument("--pg-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--poc-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; do not overwrite historical audit")
    report = audit(args.downloads, args.pg_root, args.source_root, args.poc_bundle)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "assets": len(report["offline_assets"]),
                      "poc_cache_files": report["historical_poc_bundle_cache_file_count"],
                      "release_eligible": False, "output_sha256": digest_path(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
