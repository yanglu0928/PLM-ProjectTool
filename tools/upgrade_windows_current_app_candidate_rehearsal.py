"""Rehearse an offline NON-RELEASE payload upgrade in an owned Temp root.

This tool never registers or starts services and never touches a database. A
failed switched payload is deliberately left in place until the operator calls
the explicit restore action, matching the manual-recovery release procedure.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from install_windows_current_app_candidate_rehearsal import (
    copy_and_publish, validate_candidate,
)
from package_windows_unified_candidate import digest_path

KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
ROOT_NAME = re.compile(r"plm-current-app-upgrade-[A-Za-z0-9_-]{8,64}\Z")
NEXT_NAME = re.compile(r"plm-current-app-next-[A-Za-z0-9_-]{8,64}\Z")
OWNER_FILE = ".plm-current-app-upgrade.json"
PREVIOUS_DIR = ".plm-current-app-previous"
FAILED_DIR = ".plm-current-app-failed"


def _temp_root() -> Path:
    return Path(tempfile.gettempdir()).resolve(strict=True)


def _owned_root(root: Path, owner_token: str) -> tuple[dict[str, Any], Path]:
    temp = _temp_root()
    if (root.parent.resolve(strict=True) != temp or not str(root).isascii()
            or not ROOT_NAME.fullmatch(root.name) or root.is_symlink()
            or not root.is_dir()):
        raise ValueError("owned direct ASCII Temp rehearsal root required")
    marker = root / OWNER_FILE
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("upgrade ownership record missing")
    try:
        state = json.loads(marker.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("upgrade ownership record invalid") from exc
    if (state.get("root") != str(root.resolve(strict=True))
            or state.get("owner_token") != owner_token
            or state.get("kind") != KIND):
        raise ValueError("upgrade ownership mismatch")
    return state, marker


def initialize_rehearsal(root: Path, *, owner_token: str,
                         old_candidate_sha256: str,
                         new_candidate_sha256: str) -> dict[str, Any]:
    """Bind an already verified old atomic placement to this upgrade rehearsal."""
    temp = _temp_root()
    if (root.parent.resolve(strict=True) != temp or not str(root).isascii()
            or not ROOT_NAME.fullmatch(root.name) or root.is_symlink()
            or not root.is_dir() or (root / OWNER_FILE).exists()
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", owner_token)
            or not re.fullmatch(r"[a-f0-9]{64}", old_candidate_sha256)
            or not re.fullmatch(r"[a-f0-9]{64}", new_candidate_sha256)):
        raise ValueError("fresh owned rehearsal identity required")
    for name in ("app", "data", "config", "license", "plugins"):
        path = root / name
        if path.is_symlink() or not path.is_dir():
            raise ValueError("expected isolated install directory missing")
    state: dict[str, Any] = {
        "kind": KIND,
        "root": str(root.resolve(strict=True)),
        "owner_token": owner_token,
        "old_candidate_sha256": old_candidate_sha256,
        "new_candidate_sha256": new_candidate_sha256,
        "state": "INSTALLED",
    }
    marker = root / OWNER_FILE
    with marker.open("x", encoding="ascii", newline="\n") as stream:
        json.dump(state, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return state


def _write_state(marker: Path, state: dict[str, Any]) -> None:
    temporary = marker.with_name(marker.name + ".update")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("upgrade state update path already exists")
    with temporary.open("x", encoding="ascii", newline="\n") as stream:
        json.dump(state, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, marker)


def _verify_app(app: Path, expected: dict[str, str], mapping: dict[str, str]) -> None:
    if app.is_symlink() or not app.is_dir():
        raise ValueError("application payload directory missing")
    for source_name, relative in mapping.items():
        path = app / Path(relative).relative_to("app")
        if (path.is_symlink() or not path.is_file()
                or not path.resolve(strict=True).is_relative_to(app.resolve(strict=True))
                or digest_path(path) != expected[source_name]):
            raise ValueError("application payload differs from candidate")
    actual = {path.relative_to(app.parent).as_posix()
              for path in app.rglob("*") if path.is_file()}
    if actual != set(mapping.values()):
        raise ValueError("application file inventory differs from candidate")


def upgrade_candidate(root: Path, next_root: Path, *, owner_token: str,
                      old_candidate: Path, old_candidate_sha256: str,
                      old_stage: Path, new_candidate: Path,
                      new_candidate_sha256: str, new_stage: Path,
                      fail_at: str | None = None,
                      fail_after_copy: int | None = None) -> dict[str, Any]:
    """Prepare and switch payload only; never automatically restore on failure."""
    state, marker = _owned_root(root, owner_token)
    if (state.get("state") != "INSTALLED"
            or state.get("old_candidate_sha256") != old_candidate_sha256
            or state.get("new_candidate_sha256") != new_candidate_sha256):
        raise ValueError("upgrade state or candidate identity mismatch")
    old_expected, old_mapping = validate_candidate(
        old_candidate, old_candidate_sha256, old_stage)
    new_expected, new_mapping = validate_candidate(
        new_candidate, new_candidate_sha256, new_stage)
    return upgrade_validated_payload(
        root, next_root, owner_token=owner_token,
        old_expected=old_expected, old_mapping=old_mapping,
        new_expected=new_expected, new_mapping=new_mapping,
        old_candidate_sha256=old_candidate_sha256,
        new_candidate_sha256=new_candidate_sha256,
        new_stage=new_stage, fail_at=fail_at,
        fail_after_copy=fail_after_copy,
    )


def upgrade_validated_payload(root: Path, next_root: Path, *, owner_token: str,
                              old_expected: dict[str, str], old_mapping: dict[str, str],
                              new_expected: dict[str, str], new_mapping: dict[str, str],
                              old_candidate_sha256: str, new_candidate_sha256: str,
                              new_stage: Path, fail_at: str | None = None,
                              fail_after_copy: int | None = None) -> dict[str, Any]:
    """Upgrade using candidate maps already validated in this controlled run."""
    state, marker = _owned_root(root, owner_token)
    if (state.get("state") != "INSTALLED"
            or state.get("old_candidate_sha256") != old_candidate_sha256
            or state.get("new_candidate_sha256") != new_candidate_sha256):
        raise ValueError("upgrade state or candidate identity mismatch")
    _verify_app(root / "app", old_expected, old_mapping)

    temp = _temp_root()
    if (next_root.parent.resolve(strict=True) != temp
            or not str(next_root).isascii()
            or not NEXT_NAME.fullmatch(next_root.name)
            or next_root.exists() or next_root.is_symlink()
            or next_root == root):
        raise ValueError("fresh direct ASCII Temp upgrade stage required")
    result = copy_and_publish(
        new_stage, next_root, new_expected, new_mapping,
        fail_after=fail_after_copy,
    )
    return switch_prepared_payload(
        root, next_root, owner_token=owner_token,
        old_expected=old_expected, old_mapping=old_mapping,
        new_expected=new_expected, new_mapping=new_mapping,
        old_candidate_sha256=old_candidate_sha256,
        new_candidate_sha256=new_candidate_sha256,
        result=result, fail_at=fail_at,
    )


def switch_prepared_payload(root: Path, next_root: Path, *, owner_token: str,
                            old_expected: dict[str, str], old_mapping: dict[str, str],
                            new_expected: dict[str, str], new_mapping: dict[str, str],
                            old_candidate_sha256: str, new_candidate_sha256: str,
                            result: dict[str, Any] | None = None,
                            fail_at: str | None = None) -> dict[str, Any]:
    """Switch already copied payloads; exposed for small filesystem state-machine tests."""
    state, marker = _owned_root(root, owner_token)
    if state.get("state") != "INSTALLED":
        raise ValueError("upgrade already started")
    if (state.get("old_candidate_sha256") != old_candidate_sha256
            or state.get("new_candidate_sha256") != new_candidate_sha256):
        raise ValueError("upgrade candidate identity mismatch")
    _verify_app(root / "app", old_expected, old_mapping)
    _verify_app(next_root / "app", new_expected, new_mapping)
    previous = root / PREVIOUS_DIR
    if previous.exists() or previous.is_symlink():
        raise ValueError("previous application backup path already exists")
    previous.mkdir()
    state.update({"state": "PREPARED", "next_root": str(next_root.resolve(strict=True))})
    _write_state(marker, state)
    if fail_at == "prepared":
        raise RuntimeError("injected failure after payload preparation")

    os.rename(root / "app", previous / "app")
    state["state"] = "PREVIOUS_SAVED"
    _write_state(marker, state)
    if fail_at == "previous_saved":
        raise RuntimeError("injected failure after saving previous payload")

    os.rename(next_root / "app", root / "app")
    _verify_app(root / "app", new_expected, new_mapping)
    state["state"] = "NEW_ACTIVE"
    _write_state(marker, state)
    if fail_at == "new_active":
        raise RuntimeError("injected failure after activating new payload")
    outcome = dict(result or {})
    outcome.update({"status": "NON_RELEASE_CURRENT_APP_UPGRADE_PASS",
                   "old_candidate_sha256": old_candidate_sha256,
                   "new_candidate_sha256": new_candidate_sha256,
                   "manual_restore_available": True,
                   "automatic_rollback_performed": False,
                   "services_changed": False,
                   "database_started": False,
                   "release_eligible": False})
    return outcome


def restore_previous(root: Path, *, owner_token: str,
                     old_candidate: Path, old_candidate_sha256: str,
                     old_stage: Path, new_candidate: Path,
                     new_candidate_sha256: str, new_stage: Path) -> dict[str, Any]:
    """Explicit operator action restoring the previous app payload; no data is deleted."""
    state, marker = _owned_root(root, owner_token)
    if (state.get("old_candidate_sha256") != old_candidate_sha256
            or state.get("new_candidate_sha256") != new_candidate_sha256):
        raise ValueError("restore candidate identity mismatch")
    old_expected, old_mapping = validate_candidate(
        old_candidate, old_candidate_sha256, old_stage)
    new_expected, new_mapping = validate_candidate(
        new_candidate, new_candidate_sha256, new_stage)
    return restore_prepared_payload(
        root, owner_token=owner_token, old_expected=old_expected,
        old_mapping=old_mapping, new_expected=new_expected,
        new_mapping=new_mapping, old_candidate_sha256=old_candidate_sha256,
        new_candidate_sha256=new_candidate_sha256,
    )


def restore_prepared_payload(root: Path, *, owner_token: str,
                             old_expected: dict[str, str], old_mapping: dict[str, str],
                             new_expected: dict[str, str], new_mapping: dict[str, str],
                             old_candidate_sha256: str, new_candidate_sha256: str) -> dict[str, Any]:
    """Explicit non-destructive restore primitive; quarantines the failed payload."""
    state, marker = _owned_root(root, owner_token)
    if (state.get("old_candidate_sha256") != old_candidate_sha256
            or state.get("new_candidate_sha256") != new_candidate_sha256):
        raise ValueError("restore candidate identity mismatch")
    app = root / "app"
    previous = root / PREVIOUS_DIR / "app"
    failed = root / FAILED_DIR / "app"

    if previous.is_symlink():
        raise ValueError("previous payload path is a symbolic link")
    if previous.is_dir():
        _verify_app(previous, old_expected, old_mapping)
        if app.exists() or app.is_symlink():
            _verify_app(app, new_expected, new_mapping)
            failed_parent = root / FAILED_DIR
            if failed_parent.exists() or failed_parent.is_symlink():
                raise ValueError("failed payload quarantine already exists")
            failed_parent.mkdir()
            os.rename(app, failed)
        os.rename(previous, app)
        _verify_app(app, old_expected, old_mapping)
        state["state"] = "RESTORED"
        _write_state(marker, state)
        return {"status": "NON_RELEASE_CURRENT_APP_MANUAL_RESTORE_PASS",
                "old_candidate_sha256": old_candidate_sha256,
                "failed_payload_preserved": failed.exists(),
                "automatic_rollback_performed": False,
                "release_eligible": False}

    if app.is_dir() and not app.is_symlink():
        _verify_app(app, old_expected, old_mapping)
        if state.get("state") == "RESTORED":
            return {"status": "NON_RELEASE_CURRENT_APP_MANUAL_RESTORE_ALREADY_COMPLETE",
                    "old_candidate_sha256": old_candidate_sha256,
                    "release_eligible": False}
    raise ValueError("verified previous application backup is unavailable")


def owned_paths(root: Path, owner_token: str) -> tuple[Path, ...]:
    """Return exact rehearsal-owned paths only after validating its ownership record."""
    state, _marker = _owned_root(root, owner_token)
    values = [root]
    next_root = state.get("next_root")
    if isinstance(next_root, str):
        candidate = Path(next_root)
        temp = _temp_root()
        if (candidate.parent.resolve(strict=True) == temp
                and NEXT_NAME.fullmatch(candidate.name)
                and candidate.is_dir() and not candidate.is_symlink()):
            values.append(candidate)
    return tuple(values)
