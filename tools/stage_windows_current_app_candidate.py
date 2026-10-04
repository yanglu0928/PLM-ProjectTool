"""Clean-extract a current-app NON-RELEASE ZIP into a fresh ASCII Temp child."""

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

from package_windows_current_app_candidate import SHA, SIDE_CARS
from package_windows_unified_candidate import digest_path, safe_name, zip_members
from verify_windows_unified_extract import verify, windows_long_path


KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
NAME = re.compile(r"plm-current-app-stage-[A-Za-z0-9_-]{8,64}\Z")


def stage(candidate: Path, root: Path, expected_sha256: str) -> dict[str, object]:
    temp_parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if (not SHA.fullmatch(expected_sha256) or
            root.parent.resolve(strict=True) != temp_parent or
            not str(root).isascii() or not NAME.fullmatch(root.name) or
            root.exists() or root.is_symlink()):
        raise ValueError("stage requires digest and fresh direct ASCII Temp child")
    if digest_path(candidate) != expected_sha256:
        raise ValueError("candidate ZIP digest mismatch")
    with zipfile.ZipFile(candidate) as archive:
        members = zip_members(archive)
        if not SIDE_CARS <= set(members):
            raise ValueError("candidate metadata missing")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != KIND or manifest.get("release_eligible") is not False or
                manifest.get("legal_clearance") is not False or
                manifest.get("formal_tls_material_included") is not False):
            raise ValueError("candidate release boundary differs")
        expected: dict[str, str] = {}
        folded: set[str] = set()
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, separator, name = line.partition("  ")
            safe_name(name)
            if (separator != "  " or not SHA.fullmatch(digest) or
                    not name.startswith("payload/") or name.casefold() in folded):
                raise ValueError("candidate checksum entry rejected")
            expected[name] = digest
            folded.add(name.casefold())
        if (len(expected) != manifest.get("payload_file_count") or
                set(members) != set(expected) | SIDE_CARS):
            raise ValueError("candidate inventory mismatch")
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as source, open(windows_long_path(target), "xb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
                    digest.update(block)
            if name in expected and digest.hexdigest() != expected[name]:
                raise ValueError("extracted payload mismatch: " + name)
            if name in SIDE_CARS and target.read_bytes() != archive.read(name):
                raise ValueError("extracted metadata mismatch: " + name)
    checked = verify(root, expected_kind=KIND)
    if digest_path(candidate) != expected_sha256:
        raise ValueError("candidate changed during extraction")
    return {"status": "NON_RELEASE_CURRENT_APP_CLEAN_EXTRACT_PASS",
            "candidate_sha256": expected_sha256, "stage_root": str(root),
            "payload_file_count": checked["payload_file_count"],
            "source_git_commit": manifest.get("source_git_commit"),
            "release_eligible": False, "legal_clearance": False,
            "installation_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--stage-root", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.candidate, args.stage_root, args.expected_sha256),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
