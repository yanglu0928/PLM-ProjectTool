"""Build a minimal, explicitly NON-RELEASE Windows PostgreSQL/pgvector sidecar.

This only reads a previously audited local runtime; it never initializes or
starts a database, runs a migration, installs software, or registers a service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

from audit_postgresql18_pgvector_windows_inputs import (
    PGVECTOR_COMMIT, PGVECTOR_LICENSE_SHA256, RUNTIME_FILES,
)
from package_windows_embedded_candidate import _verify_archive, digest_path
from package_windows_unified_candidate import safe_name


AUDIT_SHA256 = "15c01027e6e6feeefb3ae91c4e77d5c158d6f1bf395c4e1ba5160ec15572d0ee"
CLI_LICENSE_SHA256 = "ee3c778b2c5202a8f4733c57afacc3e025d1e0bb6be3ebe0b06f36c2f9eb202c"
KIND = "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE"
BLOCKED_SUFFIXES = {".env", ".log", ".key", ".p12", ".pfx", ".pyc"}


def select_files(pg_root: Path, source_root: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for directory in ("bin", "lib", "share"):
        root = pg_root / directory
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"runtime directory missing or linked: {directory}")
        for path in root.rglob("*"):
            if path.is_dir():
                if path.is_symlink():
                    raise ValueError("linked runtime directory rejected")
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(pg_root):
                raise ValueError("unsafe runtime file rejected")
            relative = path.relative_to(pg_root).as_posix()
            if path.suffix.lower() in BLOCKED_SUFFIXES or path.name.lower().startswith(".env"):
                raise ValueError("private or cache runtime file rejected")
            files.append((path, safe_name("payload/pgsql/" + relative)))
    for source, name, expected in (
        (pg_root / "server_license.txt", "payload/pgsql/server_license.txt", RUNTIME_FILES["server_license.txt"]),
        (pg_root / "commandlinetools_3rd_party_licenses.txt", "payload/third-party-licenses/postgresql/commandlinetools_3rd_party_licenses.txt", CLI_LICENSE_SHA256),
        (source_root / "LICENSE", "payload/third-party-licenses/pgvector/LICENSE", PGVECTOR_LICENSE_SHA256),
    ):
        if source.is_symlink() or not source.is_file() or digest_path(source) != expected:
            raise ValueError(f"license source identity mismatch: {name}")
        files.append((source, name))
    names = [name.casefold() for _, name in files]
    if len(names) != len(set(names)):
        raise ValueError("duplicate payload path")
    return sorted(files, key=lambda item: item[1])


def build(pg_root: Path, source_root: Path, audit_report: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir() or digest_path(audit_report) != AUDIT_SHA256:
        raise ValueError("pinned audit report or output parent missing")
    report = json.loads(audit_report.read_text(encoding="utf-8"))
    if (report.get("status") != "OFFLINE_INPUT_BYTES_VERIFIED_NOT_RELEASE_READY"
            or report.get("release_eligible") is not False
            or report.get("postgresql_version") != "18.6"
            or report.get("pgvector_version") != "0.8.6"
            or report.get("pgvector_source_commit") != PGVECTOR_COMMIT):
        raise ValueError("offline audit report rejected")
    version = subprocess.run([str(pg_root / "bin/pg_config.exe"), "--version"],
                             capture_output=True, text=True, timeout=15, check=False)
    if version.returncode or version.stdout.strip() != "PostgreSQL 18.6":
        raise ValueError("PostgreSQL runtime version mismatch")
    for relative, expected in RUNTIME_FILES.items():
        if digest_path(pg_root / relative) != expected:
            raise ValueError(f"pinned runtime file changed: {relative}")
    files = select_files(pg_root.resolve(strict=True), source_root.resolve(strict=True))
    if len(files) < 1000:
        raise ValueError("incomplete PostgreSQL runtime selection")
    run_root = output_parent / ("pg18-runtime-candidate-" + uuid.uuid4().hex[:12])
    run_root.mkdir()
    archive = run_root / "NOT-FOR-RELEASE-windows-pg18-pgvector-runtime.zip"
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as bundle:
        for source, name in files:
            before = digest_path(source)
            bundle.write(source, name)
            if digest_path(source) != before:
                raise ValueError(f"source changed during packaging: {name}")
            hashes[name] = before
        sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode("ascii")
        bundle.writestr("payload-sha256sums.txt", sums)
        inventory = {
            "postgresql": {"version": "18.6", "server_license": "payload/pgsql/server_license.txt",
                           "cli_third_party_licenses": "payload/third-party-licenses/postgresql/commandlinetools_3rd_party_licenses.txt"},
            "pgvector": {"version": "0.8.6", "source_commit": PGVECTOR_COMMIT,
                         "license": "payload/third-party-licenses/pgvector/LICENSE"},
            "legal_review_status": "REVIEW_REQUIRED",
        }
        inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("third-party-inventory.json", inventory_bytes)
        manifest = {
            "kind": KIND, "release_eligible": False, "installation_performed": False,
            "database_started": False, "postgresql_version": "18.6", "pgvector_version": "0.8.6",
            "pgvector_source_commit": PGVECTOR_COMMIT, "source_audit_sha256": AUDIT_SHA256,
            "payload_file_count": len(hashes), "legal_review_status": "REVIEW_REQUIRED",
            "excluded_source_directories": ["doc", "include", "pgAdmin 4", "StackBuilder", "data", "logs"],
            "known_gaps": ["formal installer and service-account ACL", "license and source obligation review",
                           "fresh isolated database functional test", "Windows Server 2025 release validation",
                           "Debian 13 release validation deferred by user"],
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("manifest.json", manifest_bytes)
    expected = {**hashes, "payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    _verify_archive(archive, expected)
    result = {"status": "NON_RELEASE_PG18_RUNTIME_INTEGRITY_PASS", "release_eligible": False,
              "archive": str(archive), "archive_sha256": digest_path(archive),
              "archive_bytes": archive.stat().st_size, "payload_file_count": len(hashes)}
    (run_root / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--audit-report", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.pg_root, args.source_root, args.audit_report, args.output_parent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
