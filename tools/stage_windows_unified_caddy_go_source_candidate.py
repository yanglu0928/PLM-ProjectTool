"""Clean-extract fixed P33 ZIP into a new direct ASCII Temp child and read back all bytes."""

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

from audit_go_stdlib_source_input import GO_LICENSE_SHA256, GO_SOURCE_SHA256
from build_windows_unified_caddy_go_source_candidate import (
    GO_LICENSE_MEMBER, GO_SOURCE_MEMBER, KIND,
)
from package_windows_unified_candidate import zip_members
from verify_windows_unified_caddy_go_source_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)
from verify_windows_unified_extract import verify as verify_stage, windows_long_path


NAME = re.compile(r"plm-caddy-go-stage-[A-Za-z0-9_-]{8,64}\Z")


def stage(candidate: Path, source: Path, root: Path) -> dict:
    parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if (root.parent.resolve(strict=True) != parent or not str(root).isascii()
            or not NAME.fullmatch(root.name) or root.exists() or root.is_symlink()):
        raise ValueError("P33 stage must be a fresh direct ASCII Temp child")
    identity = verify_candidate(candidate, source)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with zipfile.ZipFile(candidate) as archive:
        members = zip_members(archive)
        expected: dict[str, str] = {}
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            value, separator, name = line.partition("  ")
            if separator != "  " or name in expected:
                raise ValueError("P33 hash manifest line rejected")
            expected[name] = value
        if len(expected) != 21112:
            raise ValueError("P33 payload count differs")
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as inp, open(windows_long_path(target), "xb") as out:
                while block := inp.read(1024 * 1024):
                    out.write(block)
                    digest.update(block)
            if name in expected and digest.hexdigest() != expected[name]:
                raise ValueError("P33 extracted payload differs")
        for name in ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"):
            if (root / name).read_bytes() != archive.read(name):
                raise ValueError("P33 extracted metadata differs")
    checked = verify_stage(root, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("P33 staged payload count differs")
    go_source = root / GO_SOURCE_MEMBER
    go_license = root / GO_LICENSE_MEMBER
    if (hashlib.sha256(go_source.read_bytes()).hexdigest() != GO_SOURCE_SHA256
            or hashlib.sha256(go_license.read_bytes()).hexdigest() != GO_LICENSE_SHA256):
        raise ValueError("P33 staged Go source or LICENSE differs")
    with tarfile.open(go_source, "r:gz") as archive:
        version = archive.extractfile("go/VERSION")
        license_file = archive.extractfile("go/LICENSE")
        if (version is None or version.read().splitlines()[0] != b"go1.26.3"
                or license_file is None or license_file.read() != go_license.read_bytes()):
            raise ValueError("P33 staged Go source internal evidence differs")
    if verify_candidate(candidate, source) != identity:
        raise ValueError("P33 source ZIP changed after staging")
    return {"status": "NON_RELEASE_CADDY_GO_SOURCE_CLEAN_EXTRACT_PASS",
            "release_eligible": False, "candidate_sha256": ARCHIVE_SHA256,
            "stage_root": str(root), "payload_file_count": checked["payload_file_count"],
            "go_source_sha256": GO_SOURCE_SHA256, "go_license_sha256": GO_LICENSE_SHA256,
            "installation_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.candidate, args.source, args.stage_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
