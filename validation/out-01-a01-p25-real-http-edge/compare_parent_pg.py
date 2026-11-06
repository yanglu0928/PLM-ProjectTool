from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(raw: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.decode("ascii").splitlines():
        digest, sep, name = line.partition("  ")
        if sep != "  " or len(digest) != 64 or name in values:
            raise ValueError("parent package inventory is malformed")
        if not name.isascii() or name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("parent package inventory path is invalid")
        values[name] = digest.lower()
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--sidecar-sha", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if runner_temp.drive.casefold() != "d:":
        raise ValueError("parent package comparison requires D-drive runner temp")
    for candidate in (args.parent, args.sidecar, args.sidecar_sha, args.output):
        if not candidate.resolve(strict=candidate.exists()).is_relative_to(runner_temp):
            raise ValueError("comparison input escaped runner temp")

    sidecar_sha = json.loads(args.sidecar_sha.read_text(encoding="utf-8-sig"))
    expected_sidecar = (sidecar_sha.get("Hash") or sidecar_sha.get("hash") or "").lower()
    if len(expected_sidecar) != 64 or sha256_file(args.sidecar) != expected_sidecar:
        raise ValueError("same-run sidecar archive digest mismatch")

    pg_hashes: dict[str, str] = {}
    with zipfile.ZipFile(args.parent) as parent:
        names = parent.namelist()
        if len(names) != len(set(names)) or "manifest.json" not in names or "payload-sha256sums.txt" not in names:
            raise ValueError("parent candidate inventory is incomplete")
        manifest = json.loads(parent.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
                or manifest.get("release_eligible") is not False
                or manifest.get("source_commit") != args.source_commit
                or str(manifest.get("workflow_run")) != args.run_id
                or manifest.get("components", {}).get("pg18_archive_sha256") != expected_sidecar):
            raise ValueError("same-run parent candidate provenance mismatch")
        hashes = inventory(parent.read("payload-sha256sums.txt"))
        if manifest.get("payload_sha256sums_sha256") != sha256_bytes(parent.read("payload-sha256sums.txt")):
            raise ValueError("parent candidate hash inventory digest mismatch")
        for name, digest in hashes.items():
            if name.startswith("payload/pgsql/"):
                if name not in names or sha256_bytes(parent.read(name)) != digest:
                    raise ValueError("parent PostgreSQL payload hash mismatch")
                pg_hashes[name] = digest
        if not pg_hashes:
            raise ValueError("parent candidate PostgreSQL payload is empty")
        extract_root = Path(tempfile.mkdtemp(prefix="plm-out-p25-parent-pg-", dir=runner_temp))
        for name in pg_hashes:
            target = extract_root / Path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(parent.read(name))

    sidecar_hashes: dict[str, str] = {}
    with zipfile.ZipFile(args.sidecar) as sidecar:
        listed = sidecar.namelist()
        sum_name = "payload-sha256sums.txt"
        if sum_name not in listed:
            raise ValueError("sidecar payload inventory missing")
        for line in sidecar.read(sum_name).decode("ascii").splitlines():
            digest, sep, name = line.partition("  ")
            if sep == "  " and name.startswith("payload/pgsql/"):
                sidecar_hashes[name] = digest.lower()
    common = sorted(set(pg_hashes) | set(sidecar_hashes))
    same = all(pg_hashes.get(name) == sidecar_hashes.get(name) for name in common)

    initdb = extract_root / "payload" / "pgsql" / "bin" / "initdb.exe"

    def run_initdb_probe(profile: str) -> dict[str, object]:
        work = Path(tempfile.mkdtemp(prefix="plm-out-p25-profile-" + profile.lower() + "-", dir=runner_temp))
        data_dir = work / "data"
        if profile == "P25":
            command = [str(initdb), f"--pgdata={data_dir}", "--username=poc_admin",
                       "--auth=trust", "--encoding=UTF8", "--locale=C"]
        elif profile == "PARENT_SMOKE":
            command = [str(initdb), "-D", str(data_dir), "-U", "postgres",
                       "--auth-local=trust", "--auth-host=trust", "--no-locale", "-E", "UTF8"]
        else:
            raise ValueError("unknown fixed initdb profile")
        result = subprocess.run(
            command, env=os.environ.copy(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", timeout=180, check=False)
        return {
            "profile": profile,
            "exit_code": result.returncode,
            "stdout_bytes": len(result.stdout.encode("utf-8")),
            "stderr_bytes": len(result.stderr.encode("utf-8")),
            "pg_version_created": (data_dir / "PG_VERSION").is_file(),
        }

    p25_profile = run_initdb_probe("P25")
    parent_smoke_profile = run_initdb_probe("PARENT_SMOKE")
    report = {
        "status": "DIFFERENTIAL_DIAGNOSTIC",
        "run_id": args.run_id,
        "parent_pg_payload_file_count": len(pg_hashes),
        "sidecar_pg_payload_file_count": len(sidecar_hashes),
        "parent_pg_payload_matches_sidecar": same,
        "parent_pg_payload_differences": [
            {"path": name, "parent_sha256": pg_hashes.get(name), "sidecar_sha256": sidecar_hashes.get(name)}
            for name in common if pg_hashes.get(name) != sidecar_hashes.get(name)
        ][:80],
        "command_profile_comparison": {
            "same_extracted_initdb_binary": True,
            "same_original_runner_path": True,
            "p25_profile": p25_profile,
            "parent_smoke_profile": parent_smoke_profile,
        },
        "parent_candidate_initdb_exit_code": p25_profile["exit_code"],
        "runner_drive": "D:",
        "database_files_uploaded": False,
        "external_api_calls": 0,
        "plugin_executed": False,
        "release_eligible": False,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
