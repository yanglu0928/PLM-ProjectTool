"""Run the A17 packaged PlanVersion harness using only an owned hosted D-drive temp root."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
META = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
BLOCKED = {".key", ".pfx", ".p12", ".env", ".log"}


def safe_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in path.parts)
            or Path(name).suffix.casefold() in BLOCKED):
        raise ValueError("unsafe A17 candidate member")
    return path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def extract_verified(candidate: Path, expected_sha: str, stage: Path) -> int:
    if stage.exists() or stage.is_symlink() or digest(candidate) != expected_sha:
        raise ValueError("A17 candidate identity or fresh stage check failed")
    stage.mkdir()
    with zipfile.ZipFile(candidate) as archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        names = [safe_name(item.filename).as_posix() for item in infos]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("A17 archive has duplicate paths")
        if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in infos):
            raise ValueError("A17 archive symlink rejected")
        if not META <= set(names):
            raise ValueError("A17 candidate metadata missing")
        for item, name in zip(infos, names, strict=True):
            target = stage.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    sums = (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines()
    expected: dict[str, str] = {}
    for line in sums:
        sha, separator, name = line.partition("  ")
        safe_name(name)
        if separator != "  " or len(sha) != 64 or name in expected:
            raise ValueError("A17 checksum list malformed")
        expected[name] = sha
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("kind") != "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
            or manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False
            or manifest.get("payload_file_count") != len(expected)):
        raise ValueError("A17 candidate manifest rejected")
    if set(expected) | META != set(names):
        raise ValueError("A17 inventory does not match archive")
    for name, sha in expected.items():
        if digest(stage.joinpath(*PurePosixPath(name).parts)) != sha:
            raise ValueError("A17 payload checksum mismatch")
    return len(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = args.run_root.resolve()
    if (runner_temp.drive.upper() == "C:" or root.drive.upper() == "C:"
            or root.parent != runner_temp or not str(root).isascii()
            or root.exists() or root.is_symlink()):
        raise ValueError("A17 run root must be a new ASCII direct child of non-C RUNNER_TEMP")
    candidate_summary = json.loads(args.verification_summary.read_text(encoding="utf-8"))
    if (candidate_summary.get("status") != "WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS"
            or candidate_summary.get("release_eligible") is not False
            or candidate_summary.get("legal_clearance") is not False):
        raise ValueError("A17 candidate summary is not a non-release integrity pass")
    archive_sha = digest(args.candidate)
    if archive_sha != candidate_summary.get("archive_sha256"):
        raise ValueError("A17 candidate summary archive digest mismatch")

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not run_id.isascii() or not run_id.isdigit():
        raise ValueError("A17 requires a numeric hosted GITHUB_RUN_ID")
    temp_root = root / "PLMToolTemp"
    pg_temp_root = runner_temp / ("plm-p51-a27-pg-" + run_id)
    temp_root.mkdir(parents=True)
    if pg_temp_root.exists() or pg_temp_root.is_symlink():
        raise ValueError("A17 PostgreSQL temp root must be new for this workflow run")
    pg_temp_root.mkdir()
    os.environ["PLM_PG_TEMP_ROOT"] = str(pg_temp_root)
    os.environ["TEMP"] = str(temp_root)
    os.environ["TMP"] = str(temp_root)
    os.environ["PLM_P51_TEMP_ROOT"] = str(temp_root)
    os.environ["PLM_TEST_TEMP_ROOT"] = str(temp_root)
    os.environ["PYTHONPYCACHEPREFIX"] = str(temp_root / "pycache")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    stage = temp_root / ("plm-current-app-stage-" + uuid.uuid4().hex[:12])
    pristine = temp_root / "plm-install-rehearsal-a27pristine"
    target = temp_root / "plm-install-rehearsal-a27target"
    count = extract_verified(args.candidate, archive_sha, stage)
    command = [
        sys.executable, str(ROOT / "validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py"),
        "--candidate", str(args.candidate), "--stage", str(stage),
        "--pristine", str(pristine), "--target", str(target),
        "--expected-sha256", archive_sha, "--temp-root", str(temp_root),
    ]
    completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy(), text=True,
                               encoding="utf-8", errors="replace", capture_output=True,
                               timeout=5400, check=False)
    output = completed.stdout + completed.stderr
    required = ("P51_A17_PACKAGED_PLANVERSION_EDGE_PASS",
                "P51_A17_PACKAGED_PLANVERSION_PG_PASS")
    if completed.returncode or any(marker not in output for marker in required):
        raise RuntimeError("A17 packaged flow did not pass: " + output[-12000:])

    owned_root = root.resolve(strict=True)
    pg_owned_root = pg_temp_root.resolve(strict=True)
    expected_pg_root = runner_temp / ("plm-p51-a27-pg-" + run_id)
    if (owned_root.parent != runner_temp or pg_owned_root != expected_pg_root
            or pg_owned_root.is_symlink() or not str(pg_owned_root).isascii()):
        raise ValueError("A17 cleanup roots escaped this RUNNER_TEMP run")
    shutil.rmtree(pg_owned_root)
    shutil.rmtree(owned_root)
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "PASS_LIMITED",
        "flow": "A17_PACKAGED_PLANVERSION_EDGE_HTTPS_POSTGRES",
        "source_commit": candidate_summary.get("source_git_commit"),
        "candidate_sha256": archive_sha,
        "payload_file_count": count,
        "markers": [line.strip() for line in output.splitlines() if any(m in line for m in required)],
        "synthetic_identities": True,
        "customer_decisions": 0,
        "release_eligible": False,
        "legal_clearance": False,
        "runner_drive": runner_temp.drive,
        "cleanup": "OWNED_RUN_ROOT_REMOVED",
        "validation_scope": "HOSTED_WINDOWS_SERVER_2025_NOT_WINDOWS_11_DEVICE",
    }
    args.summary_out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
