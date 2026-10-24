"""Clean-extract fixed P43 ZIP into a new ASCII Temp child and read back all bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from audit_ghostscript_portable_payload import COPYING_SHA256
from audit_ghostscript_source_input import SOURCE_SHA256
from build_windows_unified_ghostscript_source_candidate import (
    KIND, LICENSE_MEMBER, LICENSE_SHA256, SOURCE_MEMBER,
)
from package_windows_unified_candidate import zip_members
from verify_windows_unified_extract import verify as verify_stage, windows_long_path
from verify_windows_unified_ghostscript_source_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)


NAME = re.compile(r"plm-gs-source-stage-[A-Za-z0-9_-]{8,64}\Z")


def stage(candidate: Path, parent: Path, ancestor: Path, root: Path) -> dict:
    temp_parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if (root.parent.resolve(strict=True) != temp_parent or not str(root).isascii()
            or not NAME.fullmatch(root.name) or root.exists() or root.is_symlink()):
        raise ValueError("P43 stage must be a fresh direct ASCII Temp child")
    identity = verify_candidate(candidate, parent, ancestor)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with zipfile.ZipFile(candidate) as archive:
        members = zip_members(archive)
        expected: dict[str, str] = {}
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            value, separator, name = line.partition("  ")
            if separator != "  " or name in expected:
                raise ValueError("P43 hash manifest line rejected")
            expected[name] = value
        if len(expected) != 21114:
            raise ValueError("P43 payload count differs")
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as inp, open(windows_long_path(target), "xb") as out:
                while block := inp.read(1024 * 1024):
                    out.write(block)
                    digest.update(block)
            if name in expected and digest.hexdigest() != expected[name]:
                raise ValueError("P43 extracted payload differs")
        for name in ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"):
            if (root / name).read_bytes() != archive.read(name):
                raise ValueError("P43 extracted metadata differs")
    checked = verify_stage(root, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("P43 staged payload count differs")
    gs_source = root / SOURCE_MEMBER
    gs_license = root / LICENSE_MEMBER
    if (hashlib.sha256(gs_source.read_bytes()).hexdigest() != SOURCE_SHA256
            or hashlib.sha256(gs_license.read_bytes()).hexdigest() != LICENSE_SHA256):
        raise ValueError("P43 staged Ghostscript source or LICENSE differs")
    with tarfile.open(gs_source, "r:xz") as source_archive:
        source_license = source_archive.extractfile("ghostscript-10.08.0/LICENSE")
        copying = source_archive.extractfile("ghostscript-10.08.0/doc/COPYING")
        if (source_license is None or source_license.read() != gs_license.read_bytes()
                or copying is None
                or hashlib.sha256(copying.read()).hexdigest() != COPYING_SHA256):
            raise ValueError("P43 staged Ghostscript internal license evidence differs")
    if verify_candidate(candidate, parent, ancestor) != identity:
        raise ValueError("P43 source ZIP changed after staging")
    return {"status": "NON_RELEASE_GHOSTSCRIPT_SOURCE_CLEAN_EXTRACT_PASS",
            "release_eligible": False, "candidate_sha256": ARCHIVE_SHA256,
            "stage_root": str(root), "payload_file_count": checked["payload_file_count"],
            "ghostscript_source_sha256": SOURCE_SHA256,
            "ghostscript_license_sha256": LICENSE_SHA256,
            "installation_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--ancestor", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.candidate, args.parent, args.ancestor, args.stage_root),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
