"""Run synthetic Evidence qualification ASGI/PG proof with bundled Python/PG18."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from package_windows_unified_candidate import digest_path
from verify_windows_unified_extract import verify


CURRENT_SHA256 = "eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7"
KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
STAGE_NAME = re.compile(r"plm-current-app-stage-[A-Za-z0-9_-]{8,64}\Z")
MARKER = "PASS: isolated PG18 source/eligibility/HTTP replay, read-only receipt lookup, single concurrent winner, template/cross-project/revoked/License denial, Audit rollback, role revoke"


def smoke(candidate: Path, stage: Path, temp_parent: Path) -> dict[str, object]:
    parent = temp_parent.resolve(strict=True)
    root = stage.resolve(strict=True)
    if (root.parent != parent or not str(root).isascii() or stage.is_symlink() or
            not STAGE_NAME.fullmatch(root.name) or digest_path(candidate) != CURRENT_SHA256):
        raise ValueError("current candidate or stage identity rejected")
    checked = verify(root, expected_kind=KIND)
    with zipfile.ZipFile(candidate) as archive:
        if (root / "manifest.json").read_bytes() != archive.read("manifest.json"):
            raise ValueError("current stage manifest differs")
    python = root / "payload/runtime/python.exe"
    pg = root / "payload/pgsql"
    script = Path(__file__).resolve().parents[1] / "validation/evd-01-a04-p03-a05/verify.py"
    if not python.is_file() or not (pg / "bin/pg_ctl.exe").is_file() or not script.is_file():
        raise ValueError("bundled runtime or Evidence validator missing")
    before = {path.name for path in parent.glob("plm-evd-elig-pg-*") if path.is_dir()}
    env = {name: value for name, value in os.environ.items()
           if not name.upper().startswith("PLM_") and name.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
    env["TEMP"] = env["TMP"] = str(parent)
    result = subprocess.run([str(python), "-I", "-B", str(script), "--packaged-pg", str(pg)],
                            capture_output=True, text=True, errors="replace", env=env,
                            timeout=300, check=False)
    after = {path.name for path in parent.glob("plm-evd-elig-pg-*") if path.is_dir()}
    if after != before:
        raise ValueError("synthetic Evidence temporary PostgreSQL files remain")
    if result.returncode or MARKER not in result.stdout.splitlines():
        raise ValueError("bundled Evidence qualification proof failed")
    if digest_path(candidate) != CURRENT_SHA256:
        raise ValueError("current candidate changed during Evidence proof")
    return {"status": "SYNTHETIC_CURRENT_APP_PACKAGED_EVIDENCE_PASS",
            "candidate_sha256": CURRENT_SHA256,
            "payload_file_count": checked["payload_file_count"],
            "packaged_python_and_pg18_used": True,
            "synthetic_asgi_project_evidence_qualification_pass": True,
            "synthetic_receipt_lookup_and_failure_matrix_pass": True,
            "temporary_database_removed": True,
            "existing_database_touched": False,
            "release_eligible": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--temp-parent", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.stage, args.temp_parent),
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
