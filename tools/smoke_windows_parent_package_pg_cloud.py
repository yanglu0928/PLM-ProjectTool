"""Run a bounded PostgreSQL component lifecycle smoke from a parent candidate on hosted Windows."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import zipfile
from pathlib import Path, PurePosixPath


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in parts)):
        raise ValueError("unsafe parent package path")
    return name


def run_checked(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"cloud smoke command failed ({Path(args[0]).name}): {result.stderr[-2000:]}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = args.work_root.resolve()
    if (root.parent != runner_temp or root.drive.casefold() == "c:"
            or root.exists() or args.archive.is_symlink()
            or not args.archive.is_file()):
        raise ValueError("smoke root must be a new runner-temp directory on a non-C drive")
    parent = json.loads(args.verification_summary.read_text(encoding="utf-8-sig"))
    if (parent.get("status") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS"
            or parent.get("release_eligible") is not False
            or parent.get("legal_clearance") is not False
            or parent.get("archive_sha256") != sha_file(args.archive)):
        raise ValueError("parent artifact summary or archive identity rejected")

    with zipfile.ZipFile(args.archive) as z:
        infos = z.infolist()
        names = [safe_name(i.filename) for i in infos]
        if len(names) != len(set(n.casefold() for n in names)):
            raise ValueError("parent archive has duplicate/case-conflicting paths")
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
            raise ValueError("parent archive symlink rejected")
        manifest = json.loads(z.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
                or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False
                or manifest.get("workflow_run") != parent.get("workflow_run")
                or manifest.get("source_commit") != parent.get("source_commit")):
            raise ValueError("parent manifest identity mismatch")
        sums = z.read("payload-sha256sums.txt")
        if sha(sums) != manifest.get("payload_sha256sums_sha256"):
            raise ValueError("parent payload checksum list identity mismatch")
        expected = {}
        for line in sums.decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            safe_name(name)
            if name in expected or len(digest) != 64:
                raise ValueError("invalid parent payload checksum list")
            expected[name] = digest
        if len(expected) != manifest.get("payload_file_count"):
            raise ValueError("parent payload count mismatch")
        if set(names) != set(expected) | {"manifest.json", "payload-sha256sums.txt"}:
            raise ValueError("parent archive inventory differs from checksum list")
        root.mkdir()
        for name, digest in expected.items():
            info = z.getinfo(name)
            target = root.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with z.open(info) as src, target.open("xb") as dst:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(block)
                    h.update(block)
            if h.hexdigest() != digest:
                raise ValueError("parent extraction hash mismatch: " + name)

    pg = root / "payload" / "pgsql"
    initdb, pg_ctl, psql = (pg / "bin" / name for name in
                            ("initdb.exe", "pg_ctl.exe", "psql.exe"))
    if not all(p.is_file() and not p.is_symlink() for p in (initdb, pg_ctl, psql)):
        raise ValueError("PostgreSQL executables missing from parent package")
    if not (pg / "lib" / "vector.dll").is_file():
        raise ValueError("pgvector extension binary missing")

    data_dir = root / "pgdata"
    log_path = root / "postgres.log"
    started = False
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    result = {}
    try:
        init = run_checked([str(initdb), "-D", str(data_dir), "-U", "postgres",
                            "--auth-local=trust", "--auth-host=trust", "--no-locale", "-E", "UTF8"], 180)
        start = run_checked([str(pg_ctl), "-D", str(data_dir), "-l", str(log_path),
                             "-o", f"-h 127.0.0.1 -p {port} -c listen_addresses=127.0.0.1",
                             "-w", "start"], 120)
        started = True
        query = run_checked([str(psql), "-h", "127.0.0.1", "-p", str(port),
                             "-U", "postgres", "-d", "postgres", "-X", "-A", "-t",
                             "-v", "ON_ERROR_STOP=1", "-c",
                             "SELECT current_setting('server_version'); CREATE EXTENSION vector; "
                             "SELECT extversion FROM pg_extension WHERE extname='vector';"], 60)
        lines = [line.strip() for line in query.stdout.splitlines() if line.strip()]
        version = lines[-2] if len(lines) >= 2 else ""
        vector_version = lines[-1] if lines else ""
        if not version.startswith("18.") or vector_version != "0.8.6":
            raise ValueError("PostgreSQL/pgvector runtime identity mismatch")
        result = {
            "status": "PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED",
            "source_commit": parent["source_commit"], "workflow_run": parent["workflow_run"],
            "parent_archive_sha256": parent["archive_sha256"],
            "postgresql_version": version, "pgvector_version": vector_version,
            "listen_host": "127.0.0.1", "temporary_database_only": True,
            "production_installation": False, "product_api_started": False,
            "license_trust_used": False, "runner_drive": root.drive,
            "parent_payload_file_count": len(expected),
        }
    finally:
        if started:
            stop = subprocess.run([str(pg_ctl), "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                                  capture_output=True, text=True, timeout=60, check=False)
            if stop.returncode:
                raise RuntimeError("temporary PostgreSQL did not stop cleanly: " + stop.stderr[-1000:])
        if root.exists():
            if root.parent != runner_temp or root.drive.casefold() == "c:":
                raise RuntimeError("refusing to clean outside runner temp/non-C drive")
            shutil.rmtree(root)

    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
