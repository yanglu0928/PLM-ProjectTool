"""Verify the PoC Ghostscript portable tree against its pinned installer bytes.

This is a byte/source inventory, not a redistribution license approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


INSTALLER_SHA256 = "52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50"
EXE_SHA256 = "9b29d3b5128c6d53bb4e9eee77e3919d05038cdfdd8e07697af4d9c319f9d5ad"
COPYING_SHA256 = "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6"
NOTICE_PATTERN = re.compile(r"(?:^|/)(?:license|copying|notice)(?:[._-]|$)", re.IGNORECASE)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def audit(installer: Path, payload: Path, sevenzip: Path, *,
          installer_sha256: str = INSTALLER_SHA256, exe_sha256: str = EXE_SHA256,
          copying_sha256: str = COPYING_SHA256, expected_count: int = 654) -> dict:
    if digest(installer) != installer_sha256:
        raise ValueError("Ghostscript installer hash mismatch")
    if digest(payload / "bin" / "gswin64c.exe") != exe_sha256:
        raise ValueError("Ghostscript CLI hash mismatch")
    if digest(payload / "doc" / "COPYING") != copying_sha256:
        raise ValueError("Ghostscript COPYING hash mismatch")
    if any(path.is_symlink() for path in payload.rglob("*")):
        raise ValueError("Ghostscript payload link rejected")
    files = sorted(path for path in payload.rglob("*") if path.is_file())
    if len(files) != expected_count:
        raise ValueError("Ghostscript payload count mismatch")
    original = {path.relative_to(payload).as_posix(): path for path in files}
    with tempfile.TemporaryDirectory(prefix="plm-gs-audit-") as temp:
        fresh = Path(temp)
        process = subprocess.run([str(sevenzip), "x", str(installer), f"-o{fresh}", "-y"],
                                 capture_output=True, text=True, timeout=120, check=False)
        if process.returncode:
            raise ValueError("Ghostscript independent extraction failed")
        if any(path.is_symlink() for path in fresh.rglob("*")):
            raise ValueError("Ghostscript fresh extraction link rejected")
        extracted = {path.relative_to(fresh).as_posix(): path
                     for path in fresh.rglob("*") if path.is_file()}
        if set(original) != set(extracted):
            raise ValueError("Ghostscript extracted path inventory mismatch")
        for name, path in original.items():
            if digest(path) != digest(extracted[name]):
                raise ValueError(f"Ghostscript extracted file mismatch: {name}")
    probe = subprocess.run([str(payload / "bin" / "gswin64c.exe"), "--version"],
                           capture_output=True, text=True, timeout=20, check=False)
    if probe.returncode or probe.stdout.strip() != "10.08.0":
        raise ValueError("Ghostscript CLI version mismatch")
    inventory = [{"path": name, "size": path.stat().st_size, "sha256": digest(path)}
                 for name, path in sorted(original.items())]
    return {
        "schema_version": "plm.ghostscript-portable-payload.v1",
        "status": "OFFICIAL_INSTALLER_PAYLOAD_BYTES_PASS_LICENSE_REVIEW_REQUIRED",
        "release_eligible": False,
        "installer_sha256": installer_sha256,
        "file_count": len(inventory),
        "payload_bytes": sum(item["size"] for item in inventory),
        "notice_paths": [item["path"] for item in inventory if NOTICE_PATTERN.search(item["path"])],
        "files": inventory,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--sevenzip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.installer, args.payload, args.sevenzip)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status", "release_eligible", "file_count", "payload_bytes", "notice_paths")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
