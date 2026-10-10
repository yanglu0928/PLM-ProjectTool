"""Clean-extract pinned P22 only into a fresh direct ASCII Temp child, then verify all bytes."""

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

from build_windows_unified_caddy_candidate import KIND
from package_windows_unified_candidate import zip_members
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify as verify_source
from verify_windows_unified_extract import verify as verify_stage, windows_long_path


NAME = re.compile(r"plm-caddy-stage-[A-Za-z0-9_-]{8,64}\Z")


def stage(candidate: Path, root: Path) -> dict:
    parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if (root.parent.resolve(strict=True) != parent or not str(root).isascii()
            or not NAME.fullmatch(root.name) or root.exists() or root.is_symlink()):
        raise ValueError("P22 stage must be a fresh direct ASCII Temp child")
    source = verify_source(candidate)  # Full ZIP check before any filesystem mutation.
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with zipfile.ZipFile(candidate) as archive:
        members = zip_members(archive)
        expected = {}
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            value, separator, name = line.partition("  ")
            if separator != "  " or name in expected:
                raise ValueError("P22 manifest line rejected")
            expected[name] = value
        if len(expected) != 21110:
            raise ValueError("P22 payload count changed")
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            value = hashlib.sha256()
            with archive.open(name) as inp, open(windows_long_path(target), "xb") as out:
                while block := inp.read(1024 * 1024):
                    out.write(block)
                    value.update(block)
            if name in expected and value.hexdigest() != expected[name]:
                raise ValueError(f"P22 extracted payload changed: {name}")
    checked = verify_stage(root, expected_kind=KIND)
    if checked["payload_file_count"] != source["payload_file_count"] or verify_source(candidate) != source:
        raise ValueError("P22 source or stage changed after extract")
    return {"status": "NON_RELEASE_CADDY_CLEAN_EXTRACT_PASS",
            "release_eligible": False, "candidate_sha256": ARCHIVE_SHA256,
            "stage_root": str(root), "payload_file_count": 21110,
            "installation_performed": False, "services_changed": False,
            "database_started": False, "tls_key_in_package": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.candidate, args.stage_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
