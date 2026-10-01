"""Verify every extracted payload byte of a unified non-release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from package_windows_unified_candidate import safe_name

ALLOWED_KINDS = {
    "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE",
    "WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE",
    "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE",
    "WINDOWS11_UNIFIED_PG18_DEVELOPMENT_CANDIDATE",
    "WINDOWS11_UNIFIED_PG18_CADDY_DEVELOPMENT_CANDIDATE",
}

def windows_long_path(path: Path) -> str:
    absolute = str(path.resolve())
    return "\\\\?\\" + absolute if os.name == "nt" and not absolute.startswith("\\\\?\\") else absolute


def verify(root: Path, *, expected_kind: str = "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE") -> dict:
    if expected_kind not in ALLOWED_KINDS:
        raise ValueError("unknown candidate kind")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("kind") != expected_kind or manifest.get("release_eligible") is not False:
        raise ValueError("not a non-release unified candidate")
    lines = (root / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines()
    expected: dict[str, str] = {}
    for line in lines:
        digest, separator, name = line.partition("  ")
        safe_name(name)
        if separator != "  " or len(digest) != 64 or name.casefold() in expected:
            raise ValueError("invalid or duplicate hash entry")
        expected[name.casefold()] = digest
        path = root / name
        with open(windows_long_path(path), "rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise ValueError(f"extracted payload hash mismatch: {name}")
    if len(expected) != manifest.get("payload_file_count"):
        raise ValueError("payload count mismatch")
    long_root = windows_long_path(root)
    actual_names = {
        (Path(os.path.relpath(folder, long_root)) / filename).as_posix().casefold()
        for folder, _, filenames in os.walk(long_root) for filename in filenames
    }
    complete = set(expected) | {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
    if actual_names != complete:
        raise ValueError(f"extracted file set differs: missing={len(complete - actual_names)} extra={len(actual_names - complete)}")
    return {"status": "CLEAN_EXTRACT_HASH_PASS", "payload_file_count": len(expected), "release_eligible": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-kind", choices=sorted(ALLOWED_KINDS),
                        default="WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, expected_kind=args.expected_kind), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
