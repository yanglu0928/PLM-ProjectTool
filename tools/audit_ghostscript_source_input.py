"""Verify the official Ghostscript 10.08.0 source input against fixed P33.

This proves archive identity and package provenance, not a reproducible build,
complete corresponding-source obligations, or legal clearance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from audit_ghostscript_portable_payload import COPYING_SHA256, INSTALLER_SHA256
from verify_windows_unified_caddy_go_source_candidate import verify


SOURCE_SHA256 = "c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf"
SOURCE_BYTES = 69197208
SOURCE_MEMBERS = 9398
SOURCE_FILES = 8681
ROOT = "ghostscript-10.08.0"
COPYING_MEMBER = f"{ROOT}/doc/COPYING"
CANDIDATE_COPYING = "payload/ocr/ghostscript/doc/COPYING"
REQUIRED = (
    f"{ROOT}/LICENSE", f"{ROOT}/README", f"{ROOT}/Makefile.in",
    f"{ROOT}/psi/msvc.mak", f"{ROOT}/windows/ghostscript.vcxproj",
    COPYING_MEMBER,
)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def inspect_source(source: Path, *, expected_sha256: str = SOURCE_SHA256,
                   expected_bytes: int = SOURCE_BYTES,
                   expected_members: int = SOURCE_MEMBERS,
                   expected_files: int = SOURCE_FILES,
                   expected_copying: str = COPYING_SHA256,
                   root: str = ROOT, required: tuple[str, ...] = REQUIRED) -> dict:
    if not source.is_file() or source.stat().st_size != expected_bytes:
        raise ValueError("Ghostscript source archive size mismatch")
    if digest(source) != expected_sha256:
        raise ValueError("Ghostscript source archive SHA-256 mismatch")
    with tarfile.open(source, "r:xz") as archive:
        members = archive.getmembers()
        names = [item.name for item in members]
        if (len(members) != expected_members or len(names) != len(set(names))
                or sum(item.isfile() for item in members) != expected_files
                or any(not (item.isfile() or item.isdir()) for item in members)):
            raise ValueError("Ghostscript source member inventory mismatch")
        for name in names:
            path = PurePosixPath(name)
            if (path.is_absolute() or "\\" in name or ".." in path.parts
                    or not path.parts or path.parts[0] != root):
                raise ValueError("Ghostscript source member path rejected")
        if any(name not in names for name in required):
            raise ValueError("Ghostscript source build or license file missing")
        copying = archive.extractfile(f"{root}/doc/COPYING")
        if copying is None or hashlib.sha256(copying.read()).hexdigest() != expected_copying:
            raise ValueError("Ghostscript source AGPL text differs from installed payload")
    return {"source_sha256": expected_sha256, "source_bytes": expected_bytes,
            "archive_members": len(members), "regular_files": expected_files,
            "agpl_copying_sha256": expected_copying,
            "windows_build_metadata_present": True}


def audit(candidate: Path, parent: Path, source: Path) -> dict:
    identity = verify(candidate, parent)
    inspected = inspect_source(source)
    with zipfile.ZipFile(candidate) as archive:
        names = set(archive.namelist())
        if (CANDIDATE_COPYING not in names
                or hashlib.sha256(archive.read(CANDIDATE_COPYING)).hexdigest() != COPYING_SHA256
                or any(name.startswith("payload/third-party-sources/ghostscript/") for name in names)):
            raise ValueError("fixed candidate Ghostscript evidence boundary differs")
    return {"status": "OFFICIAL_GHOSTSCRIPT_SOURCE_INPUT_VERIFIED_NOT_BUNDLED",
            "release_eligible": False, "legal_clearance": False,
            "candidate_sha256": identity["archive_sha256"],
            "candidate_payload_file_count": identity["payload_file_count"],
            "matching_official_windows_installer_sha256": INSTALLER_SHA256,
            **inspected, "source_in_fixed_candidate": False,
            "reproducible_windows_binary_build_verified": False,
            "complete_corresponding_source_obligations_reviewed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.parent, args.source),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
