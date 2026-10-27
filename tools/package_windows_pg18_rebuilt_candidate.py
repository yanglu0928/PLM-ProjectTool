"""Package a newly cloud-built, NON-RELEASE PostgreSQL 18.6/pgvector sidecar.

Unlike the historical P12 builder, this consumes fresh official-source evidence
and a freshly compiled extension instead of pinning a machine-local audit JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import uuid
import zipfile
from pathlib import Path, PurePosixPath


PGVECTOR_COMMIT = "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
PG_BINARY_ARCHIVE = {
    "name": "postgresql-18.6-1-windows-x64-binaries.zip",
    "size": 343808005,
    "sha256": "fbe23da234ee31547bf8a36d29dfd81e82b849df2d2b78d2eecb43d360252f8c",
}
PGVECTOR_SOURCE_ARCHIVE = {
    "name": "pgvector-0.8.6.zip",
    "size": 214357,
    "sha256": "250f5f488a5e512c8781c338608dfac32ae34f97088970a1b5bb8f5be797caf8",
}
RUNTIME_TEXT_HASHES = {
    "server_license.txt": "39294f3f5b41533b307e118ee37c356f32cbc7746fc97e8b91f1b49a9068a24e",
}
CLI_LICENSE_SHA256 = "ee3c778b2c5202a8f4733c57afacc3e025d1e0bb6be3ebe0b06f36c2f9eb202c"
PGVECTOR_LICENSE_SHA256 = "8e9a3fcc1aae0eba1d07bf8eb27de9a055baecdf1a31390cf6f2af1ab73c1802"
BLOCKED_SUFFIXES = {".env", ".log", ".key", ".p12", ".pfx", ".pyc"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(value: str) -> str:
    parts = PurePosixPath(value).parts
    if (not value or value.startswith(("/", "\\")) or "\\" in value or ":" in value
            or any(part in ("", ".", "..") for part in parts)):
        raise ValueError(f"unsafe archive path: {value!r}")
    return value


def official_inputs(downloads: Path) -> dict:
    inputs = []
    for spec in (PG_BINARY_ARCHIVE, PGVECTOR_SOURCE_ARCHIVE):
        path = downloads / spec["name"]
        if (not path.is_file() or path.stat().st_size != spec["size"]
                or digest(path) != spec["sha256"]):
            raise ValueError(f"official input identity mismatch: {spec['name']}")
        inputs.append({"name": spec["name"], "size_bytes": spec["size"], "sha256": spec["sha256"]})
    return {"edb_binary_archive": inputs[0], "pgvector_source_archive": inputs[1]}


def select_payload(pg_root: Path, source_root: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    root = pg_root.resolve(strict=True)
    for directory in ("bin", "lib", "share"):
        base = pg_root / directory
        if not base.is_dir() or base.is_symlink():
            raise ValueError(f"PostgreSQL runtime directory missing: {directory}")
        for path in base.rglob("*"):
            if path.is_dir():
                if path.is_symlink():
                    raise ValueError("runtime directory symlink rejected")
                continue
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise ValueError("runtime file escapes root")
            rel = path.relative_to(pg_root).as_posix()
            if path.suffix.lower() in BLOCKED_SUFFIXES or path.name.lower().startswith(".env"):
                raise ValueError(f"runtime private/generated file rejected: {rel}")
            files.append((path, safe_name("payload/pgsql/" + rel)))
    for source, target, expected in (
        (pg_root / "server_license.txt", "payload/pgsql/server_license.txt",
         RUNTIME_TEXT_HASHES["server_license.txt"]),
        (pg_root / "commandlinetools_3rd_party_licenses.txt",
         "payload/third-party-licenses/postgresql/commandlinetools_3rd_party_licenses.txt",
         CLI_LICENSE_SHA256),
        (source_root / "LICENSE", "payload/third-party-licenses/pgvector/LICENSE",
         PGVECTOR_LICENSE_SHA256),
    ):
        if source.is_symlink() or not source.is_file() or digest(source) != expected:
            raise ValueError(f"license text differs from pinned source: {target}")
        files.append((source, target))
    folded = [name.casefold() for _, name in files]
    if len(folded) != len(set(folded)):
        raise ValueError("case-insensitive payload collision")
    return sorted(files, key=lambda item: item[1])


def build(downloads: Path, pg_root: Path, source_root: Path, output_parent: Path) -> dict:
    if not output_parent.is_dir() or output_parent.is_symlink():
        raise ValueError("output parent must be an existing real directory")
    inputs = official_inputs(downloads)
    source_root = source_root.resolve(strict=True)
    pg_root = pg_root.resolve(strict=True)
    if not (source_root / ".git").is_dir():
        raise ValueError("pgvector Git checkout required")
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=20, check=False)
    if commit.returncode or commit.stdout.strip() != PGVECTOR_COMMIT:
        raise ValueError("pgvector source commit differs from the approved tag")
    version = subprocess.run(
        [str(pg_root / "bin/pg_config.exe"), "--version"],
        capture_output=True, text=True, timeout=20, check=False)
    if version.returncode or version.stdout.strip() != "PostgreSQL 18.6":
        raise ValueError("PostgreSQL runtime version mismatch")
    vector_control = pg_root / "share/extension/vector.control"
    if (not vector_control.is_file()
            or "default_version = '0.8.6'" not in vector_control.read_text(encoding="utf-8")):
        raise ValueError("installed pgvector extension version mismatch")
    vector_dll = pg_root / "lib/vector.dll"
    if not vector_dll.is_file():
        raise ValueError("compiled pgvector extension DLL missing")
    compiler = os.environ.get("PLM_PG18_BUILD_TOOLCHAIN", "MSVC/AMD64 (runner detected)")
    files = select_payload(pg_root, source_root)
    if len(files) < 1000:
        raise ValueError("PostgreSQL runtime selection is incomplete")
    run = output_parent / ("pg18-rebuilt-" + uuid.uuid4().hex[:12])
    run.mkdir(mode=0o700)
    archive = run / "NOT-FOR-RELEASE-windows-pg18-pgvector-runtime.zip"
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as bundle:
        for path, name in files:
            before = digest(path)
            bundle.write(path, name)
            if digest(path) != before:
                raise ValueError(f"source changed while packaging: {name}")
            hashes[name] = before
        sums = "".join(f"{value}  {name}\n" for name, value in sorted(hashes.items())).encode("ascii")
        bundle.writestr("payload-sha256sums.txt", sums)
        inventory = {
            "schema_version": "plm.third-party-inventory.v1",
            "review_status": "REVIEW_REQUIRED",
            "postgresql": {"version": "18.6", "binary_archive_sha256": inputs["edb_binary_archive"]["sha256"]},
            "pgvector": {"version": "0.8.6", "source_commit": PGVECTOR_COMMIT,
                         "source_archive_sha256": inputs["pgvector_source_archive"]["sha256"],
                         "compiled_vector_dll_sha256": digest(vector_dll)},
        }
        inventory_bytes = (json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("third-party-inventory.json", inventory_bytes)
        manifest = {
            "kind": "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE_REBUILT",
            "schema_version": "plm.windows-pg18-runtime.v2",
            "release_eligible": False, "legal_clearance": False,
            "installation_performed": False, "database_started": False,
            "postgresql_version": "18.6", "pgvector_version": "0.8.6",
            "pgvector_source_commit": PGVECTOR_COMMIT,
            "pgvector_compiled_dll_sha256": digest(vector_dll),
            "build_toolchain": compiler, "source_inputs": inputs,
            "payload_file_count": len(hashes), "review_status": "REVIEW_REQUIRED",
            "known_gaps": [
                "formal installer, service account and ACL are not included",
                "third-party legal review remains open",
                "this artifact has not been installed or started",
                "Windows Server product acceptance, Gate 3 through UAT remain open",
                "Debian 13 verification is deferred by user but remains a target",
            ],
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        bundle.writestr("manifest.json", manifest_bytes)
    expected = {**hashes,
                "payload-sha256sums.txt": hashlib.sha256(sums).hexdigest(),
                "third-party-inventory.json": hashlib.sha256(inventory_bytes).hexdigest(),
                "manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.namelist()) != len(expected) or set(bundle.namelist()) != set(expected):
            raise ValueError("rebuilt sidecar inventory mismatch")
        for name, expected_hash in expected.items():
            with bundle.open(name) as stream:
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected_hash:
                raise ValueError(f"rebuilt sidecar readback hash mismatch: {name}")
    result = {
        "status": "NON_RELEASE_PG18_RUNTIME_REBUILT_INTEGRITY_PASS",
        "release_eligible": False, "legal_clearance": False,
        "archive": str(archive), "archive_sha256": digest(archive),
        "archive_bytes": archive.stat().st_size, "payload_file_count": len(hashes),
        "pgvector_dll_sha256": digest(vector_dll),
        "postgresql_binary_sha256": inputs["edb_binary_archive"]["sha256"],
        "pgvector_source_commit": PGVECTOR_COMMIT,
    }
    (run / "verification-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--pg-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-parent", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.downloads, args.pg_root, args.source_root, args.output_parent),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
