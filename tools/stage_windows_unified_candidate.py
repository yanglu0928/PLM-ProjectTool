"""Stage the pinned NON-RELEASE ZIP only in a fresh ASCII temp directory.

This is an isolated rehearsal, never a product installation or upgrade.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from package_windows_unified_candidate import zip_members
from plan_windows_unified_install import digest_archive, inspect_candidate
from verify_windows_unified_extract import verify, windows_long_path
from windows_install_root_preflight import validate_install_root


STAGE_NAME = re.compile(r"plm-unified-stage-[A-Za-z0-9_-]{8,64}\Z")


def validate_stage_root(root: Path, *, temp_parent: Path | None = None) -> Path:
    if not isinstance(root, Path):
        raise ValueError("staging root must be a Path")
    raw = str(root)
    validate_install_root(raw)
    if not STAGE_NAME.fullmatch(root.name):
        raise ValueError("staging root name rejected")
    allowed = (temp_parent or Path(tempfile.gettempdir())).resolve(strict=True)
    if not str(allowed).isascii() or root.parent.resolve(strict=True) != allowed:
        raise ValueError("staging root must be a direct child of the ASCII temp directory")
    if root.exists() or root.is_symlink():
        raise ValueError("staging root must not exist")
    return root


def stage(archive_path: Path, stage_root: Path) -> dict:
    root = validate_stage_root(stage_root)
    source_report = inspect_candidate(archive_path)  # Full source check before any writes.
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    expected: dict[str, str] = {}
    with zipfile.ZipFile(archive_path) as archive:
        members = zip_members(archive)
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, _, name = line.partition("  ")
            expected[name] = digest
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as source, open(windows_long_path(target), "xb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
                    digest.update(block)
            if name in expected and digest.hexdigest() != expected[name]:
                raise ValueError(f"staging hash mismatch: {name}")
    result = verify(root)  # Re-read every staged file and reject missing/extra files.
    if digest_archive(archive_path) != source_report["candidate_sha256"]:
        raise ValueError("candidate archive changed during staging")
    if result["payload_file_count"] != source_report["payload_file_count"]:
        raise ValueError("staging count differs from source")
    return {"status": "NON_RELEASE_STAGING_PASS", "stage_root": str(root),
            "candidate_sha256": source_report["candidate_sha256"],
            "payload_file_count": result["payload_file_count"],
            "installation_performed": False, "install_authorized": False,
            "release_eligible": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--stage-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = stage(args.candidate, args.stage_root)
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeDecodeError) as error:
        print(json.dumps({"status": "STAGING_REJECTED", "reason": str(error),
                          "installation_performed": False, "release_eligible": False},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
