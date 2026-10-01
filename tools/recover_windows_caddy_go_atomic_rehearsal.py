"""Inspect or quarantine an interrupted P39 non-release Temp install copy.

Quarantine is a same-volume rename, not deletion, installation, or rollback.
Unknown or modified roots are reported only and never moved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from install_windows_caddy_go_atomic_rehearsal import INTENT_SUFFIX
from rehearse_windows_unified_pg18_layout import ROOT_NAME
from verify_windows_unified_caddy_go_source_candidate import ARCHIVE_SHA256


PARTIAL_NAME = re.compile(r"plm-p39-partial-[A-Za-z0-9_-]{8,64}\Z")


def _temp_child(path: Path) -> bool:
    try:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        return path.parent.resolve(strict=True) == temp and str(path).isascii()
    except OSError:
        return False


def inspect(partial: Path) -> dict:
    if not _temp_child(partial) or not PARTIAL_NAME.fullmatch(partial.name):
        raise ValueError("partial path outside fixed ASCII Temp scope")
    marker = Path(str(partial) + INTENT_SUFFIX)
    base = {"partial_name": partial.name, "release_eligible": False,
            "file_deleted": False, "service_changed": False}
    if partial.is_symlink() or marker.is_symlink() or (
            partial.exists() and (not partial.is_dir() or any(item.is_symlink() for item in partial.rglob("*")))):
        return {**base, "status": "UNSAFE_PATH_REJECTED"}
    if not marker.is_file():
        return {**base, "status": "UNCLAIMED_PARTIAL" if partial.is_dir() else "NOT_FOUND"}
    try:
        intent = json.loads(marker.read_text(encoding="ascii"))
        if (type(intent) is not dict or set(intent) != {
                "schema_version", "partial_name", "target_root", "candidate_sha256"}
                or intent["schema_version"] != 1
                or intent["partial_name"] != partial.name
                or intent["candidate_sha256"] != ARCHIVE_SHA256
                or type(intent["target_root"]) is not str):
            raise ValueError("invalid intent")
        target = Path(intent["target_root"])
        if (not _temp_child(target) or not ROOT_NAME.fullmatch(target.name)
                or target == partial or target.is_symlink()):
            raise ValueError("unsafe target in intent")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return {**base, "status": "INVALID_INTENT_REJECTED"}
    if partial.is_dir() and not target.exists():
        status = "OWNED_INCOMPLETE_PARTIAL"
    elif not partial.exists() and target.is_dir():
        status = "PUBLISHED_WITH_STALE_INTENT"
    elif not partial.exists() and not target.exists():
        status = "INTENT_WITHOUT_PAYLOAD"
    else:
        status = "AMBIGUOUS_STATE_REJECTED"
    return {**base, "status": status, "target_name": target.name}


def discover() -> list[dict]:
    root = Path(tempfile.gettempdir()).resolve(strict=True)
    names = {path.name.removesuffix(INTENT_SUFFIX) for path in root.glob("plm-p39-partial-*")
             if PARTIAL_NAME.fullmatch(path.name.removesuffix(INTENT_SUFFIX))}
    return [inspect(root / name) for name in sorted(names)]


def quarantine(partial: Path) -> dict:
    state = inspect(partial)
    if state["status"] != "OWNED_INCOMPLETE_PARTIAL":
        raise ValueError("only owned incomplete partials can be quarantined")
    root = Path(tempfile.gettempdir()).resolve(strict=True)
    marker = Path(str(partial) + INTENT_SUFFIX)
    destination = root / f"plm-p39-quarantine-{uuid.uuid4().hex}"
    destination_marker = Path(str(destination) + INTENT_SUFFIX)
    if destination.exists() or destination_marker.exists():
        raise ValueError("quarantine destination collision")
    # Re-check immediately before the reversible move. Unknown changes fail closed.
    if inspect(partial) != state:
        raise ValueError("partial changed during inspection")
    os.rename(partial, destination)
    try:
        os.rename(marker, destination_marker)
    except OSError:
        # Both are preserved; the original marker now points to a missing partial.
        # No automatic deletion or broader move is attempted.
        raise
    return {"status": "INCOMPLETE_PARTIAL_QUARANTINED",
            "quarantine_name": destination.name, "release_eligible": False,
            "file_deleted": False, "target_written": False,
            "service_changed": False, "database_connected": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--discover", action="store_true")
    action.add_argument("--inspect", type=Path)
    action.add_argument("--quarantine", type=Path)
    args = parser.parse_args()
    try:
        result = (discover() if args.discover else
                  inspect(args.inspect) if args.inspect else quarantine(args.quarantine))
    except (OSError, ValueError):
        print(json.dumps({"status": "RECOVERY_REJECTED", "release_eligible": False}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
