"""Read-only installation plan for a pinned Windows NON-RELEASE candidate.

No extraction, service registration, database migration, or file mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from package_windows_unified_candidate import safe_name, zip_members
from windows_install_root_preflight import validate_install_root


CANDIDATE_SHA256 = "da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff"
REQUIRED_MEMBERS = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
OPEN_GATES = [
    "product License/public key and signing provenance",
    "third-party NOTICE/corresponding source and legal review",
    "PostgreSQL 18/pgvector offline installation and target account",
    "HTTPS/ACL/three Windows services and restart checks",
    "target backup/restore and migration quiescence evidence",
    "real document quality, Windows Server 2025 and release gates",
]


def digest_archive(archive: Path) -> str:
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_candidate(archive_path: Path, *, expected_sha256: str = CANDIDATE_SHA256) -> dict:
    if digest_archive(archive_path) != expected_sha256:
        raise ValueError("candidate archive identity mismatch")
    with zipfile.ZipFile(archive_path) as archive:
        members = zip_members(archive)
        if not REQUIRED_MEMBERS <= set(members):
            raise ValueError("candidate metadata missing")
        if any(name not in REQUIRED_MEMBERS and not name.startswith("payload/") for name in members):
            raise ValueError("candidate has unexpected top-level file")
        if sum(item.file_size for item in members.values()) > 3 * 1024**3:
            raise ValueError("candidate expanded size exceeds limit")
        manifest = json.loads(archive.read("manifest.json"))
        inventory = json.loads(archive.read("third-party-inventory.json"))
        if (manifest.get("kind") != "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE"
                or manifest.get("release_eligible") is not False
                or manifest.get("vendored_python_distributions") != 106
                or manifest.get("no_jbig_pe_count") != 34
                or manifest.get("old_tesseract_included") is not False
                or inventory.get("distribution_count") != 106
                or inventory.get("status") != "REVIEW_REQUIRED"):
            raise ValueError("candidate metadata contradicts pinned non-release scope")
        lines = archive.read("payload-sha256sums.txt").decode("ascii").splitlines()
        expected: dict[str, str] = {}
        for line in lines:
            digest, separator, name = line.partition("  ")
            safe_name(name)
            if (separator != "  " or len(digest) != 64
                    or any(char not in "0123456789abcdef" for char in digest)
                    or not name.startswith("payload/") or name.casefold() in expected):
                raise ValueError("candidate hash manifest rejected")
            expected[name.casefold()] = digest
        if (set(expected) != {name.casefold() for name in members if name not in REQUIRED_MEMBERS}
                or len(expected) != manifest.get("payload_file_count")):
            raise ValueError("candidate payload inventory mismatch")
        for name in members:
            if name in REQUIRED_MEMBERS:
                continue
            digest = hashlib.sha256()
            with archive.open(name) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected[name.casefold()]:
                raise ValueError(f"candidate payload hash mismatch: {name}")
    return {"candidate_sha256": expected_sha256, "payload_file_count": len(expected),
            "vendored_python_distributions": 106, "no_jbig_pe_count": 34}


def plan(archive_path: Path, install_root: str) -> dict:
    root = validate_install_root(install_root)  # Must be first; no archive I/O on invalid target.
    inspection = inspect_candidate(archive_path)
    return {"status": "NON_RELEASE_READ_ONLY_INSTALL_PLAN", "install_authorized": False,
            "release_eligible": False, "install_root": root, **inspection,
            "proposed_steps": ["offline dependency and trust-source verification",
                               "safe staging after all gates close", "database and data-root setup",
                               "explicit service registration", "restart and end-to-end acceptance"],
            "open_gates": OPEN_GATES}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args()
    try:
        result = plan(args.candidate, args.install_root)
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeDecodeError) as error:
        print(json.dumps({"status": "INSTALL_PLAN_REJECTED", "reason": str(error),
                          "install_authorized": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
