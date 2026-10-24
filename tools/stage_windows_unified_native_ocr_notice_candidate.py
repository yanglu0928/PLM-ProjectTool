"""Clean-extract the fixed native OCR notice candidate into a fresh ASCII Temp child."""

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

from build_windows_unified_native_ocr_notice_candidate import KIND, INDEX, PREFIX, README
from package_windows_unified_candidate import zip_members
from verify_windows_unified_extract import verify as verify_stage, windows_long_path
from verify_windows_unified_native_ocr_notice_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)


NAME = re.compile(r"plm-native-ocr-stage-[A-Za-z0-9_-]{8,64}\Z")
METADATA = ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json")


def stage(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
          native_matrix: Path, root: Path) -> dict:
    temp_parent = Path(tempfile.gettempdir()).resolve(strict=True)
    if (root.parent.resolve(strict=True) != temp_parent or not str(root).isascii()
            or not NAME.fullmatch(root.name) or root.exists() or root.is_symlink()):
        raise ValueError("native OCR stage must be a fresh direct ASCII Temp child")
    identity = verify_candidate(candidate, parent, ancestor, grandparent, native_matrix)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with zipfile.ZipFile(candidate) as archive:
        members = zip_members(archive)
        expected: dict[str, str] = {}
        folded: set[str] = set()
        for line in archive.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, separator, name = line.partition("  ")
            if separator != "  " or name.casefold() in folded:
                raise ValueError("native OCR hash manifest line rejected")
            expected[name] = digest
            folded.add(name.casefold())
        if len(expected) != 21158 or set(members) != set(expected) | set(METADATA):
            raise ValueError("native OCR ZIP file set differs")
        for name in sorted(members):
            target = root / name
            os.makedirs(windows_long_path(target.parent), exist_ok=True)
            digest = hashlib.sha256()
            with archive.open(name) as source, open(windows_long_path(target), "xb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
                    digest.update(block)
            if name in expected and digest.hexdigest() != expected[name]:
                raise ValueError("native OCR extracted payload differs")
        for name in METADATA:
            if (root / name).read_bytes() != archive.read(name):
                raise ValueError("native OCR extracted metadata differs")
    checked = verify_stage(root, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("native OCR staged count differs")
    review = json.loads((root / INDEX).read_text(encoding="utf-8"))
    if (len(review["evidence"]) != 61 or review["unique_text_count"] != 42
            or review["legal_clearance"] is not False
            or review["release_eligible"] is not False):
        raise ValueError("native OCR staged review boundary differs")
    if not (root / README).read_bytes().startswith(b"Native OCR third-party license-text review inputs."):
        raise ValueError("native OCR staged README differs")
    for item in review["evidence"]:
        path = item["text_path"]
        if not path.startswith(PREFIX + "texts/"):
            raise ValueError("native OCR staged text path differs")
        with open(windows_long_path(root / path), "rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != item["text_sha256"]:
                raise ValueError("native OCR staged text differs")
    if verify_candidate(candidate, parent, ancestor, grandparent, native_matrix) != identity:
        raise ValueError("native OCR source ZIP changed after staging")
    return {"status": "NON_RELEASE_NATIVE_OCR_NOTICE_CLEAN_EXTRACT_PASS",
            "candidate_sha256": ARCHIVE_SHA256, "stage_root": str(root),
            "payload_file_count": checked["payload_file_count"],
            "license_text_count": 42, "evidence_record_count": 61,
            "release_eligible": False, "legal_clearance": False,
            "installation_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix", "stage-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.candidate, args.parent, args.ancestor, args.grandparent,
                           args.native_matrix, args.stage_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
