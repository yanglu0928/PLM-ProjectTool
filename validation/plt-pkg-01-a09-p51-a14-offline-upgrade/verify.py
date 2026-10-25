from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from install_windows_current_app_candidate_rehearsal import (  # noqa: E402
    candidate_inventory,
    copy_and_publish,
)
from upgrade_windows_current_app_candidate_rehearsal import (  # noqa: E402
    initialize_rehearsal,
    restore_prepared_payload,
    upgrade_validated_payload,
)

OLD_SHA = "4f090636986c5c2173a5fde48eb161a94e5ee285ce73a8deb529c8682e048f46"
NEW_SHA = "3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455"
OLD_ZIP = ROOT / "artifacts/package-prep/windows11/current-app-sur-a08-20261025/current-app-candidate-4eaa7f158bed/NOT-FOR-RELEASE-windows11-current-app.zip"
NEW_ZIP = ROOT / "artifacts/package-prep/windows11/current-app-p51-a02-20261025/output/current-app-candidate-96313d4e1215/NOT-FOR-RELEASE-windows11-current-app.zip"
OLD_STAGE = Path(r"D:\PLMToolTemp\plm-current-app-stage-sura08-fixed")
NEW_STAGE = Path(r"D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e")


def _snapshot(root: Path) -> dict[str, tuple[str, str]]:
    return {
        path.relative_to(root).as_posix(): (hashlib.sha256(path.read_bytes()).hexdigest(), str(path.stat().st_size))
        for folder in ("data", "config", "license", "plugins")
        for path in (root / folder).rglob("*") if path.is_file()
    }


def _seed(root: Path, token: str) -> dict[str, tuple[str, str]]:
    for folder in ("data", "config", "license", "plugins"):
        marker = root / folder / f"synthetic-{token}.marker"
        marker.write_text(f"synthetic-only:{folder}:{token}\n", encoding="ascii", newline="\n")
    return _snapshot(root)


def _remove_owned(root: Path, next_root: Path, token: str,
                  *, root_created_by_this_run: bool) -> None:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    for path, prefix in ((root, "plm-current-app-upgrade-"),
                         (next_root, "plm-current-app-next-")):
        if not path.exists():
            continue
        if (path.parent.resolve(strict=True) != temp or not str(path).isascii()
                or not path.name.startswith(prefix) or not path.is_dir() or path.is_symlink()):
            raise RuntimeError("refusing cleanup outside exact rehearsal-owned Temp paths")
        if path == root and root_created_by_this_run:
            marker = path / ".plm-current-app-upgrade.json"
            if marker.exists() and (not marker.is_file()
                    or json.loads(marker.read_text(encoding="ascii")).get("owner_token") != token):
                raise RuntimeError("refusing cleanup without matching owner marker")
        elif path == root:
            raise RuntimeError("refusing cleanup of a root not created by this run")
        shutil.rmtree(path)


def _one_run(temp: Path, suffix: str, *, inject_failure: bool) -> dict[str, object]:
    token = secrets.token_urlsafe(24).replace("-", "_")
    root = temp / f"plm-current-app-upgrade-{suffix}-{uuid.uuid4().hex[:12]}"
    next_root = temp / f"plm-current-app-next-{suffix}-{uuid.uuid4().hex[:12]}"
    if not root.name.isascii() or root.exists() or next_root.exists():
        raise RuntimeError("fresh ASCII Temp paths required")
    candidate_stats = [(path.stat().st_size, path.stat().st_mtime_ns)
                       for path in (OLD_ZIP, NEW_ZIP)]
    old_expected, old_mapping = candidate_inventory(
        OLD_ZIP, OLD_SHA, prior_attestation=OLD_ZIP.parent / "verification-summary.json")
    new_expected, new_mapping = candidate_inventory(
        NEW_ZIP, NEW_SHA, prior_attestation=NEW_ZIP.parent / "verification-summary.json")
    root_created_by_this_run = False
    try:
        placement = copy_and_publish(OLD_STAGE, root, old_expected, old_mapping)
        if placement.get("status") != "NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_PASS":
            raise RuntimeError("old candidate atomic placement failed")
        root_created_by_this_run = True
        (root / "config").mkdir(exist_ok=False)
        markers = _seed(root, token)
        initialize_rehearsal(root, owner_token=token,
                             old_candidate_sha256=OLD_SHA,
                             new_candidate_sha256=NEW_SHA)
        if inject_failure:
            try:
                upgrade_validated_payload(
                    root, next_root, owner_token=token,
                    old_expected=old_expected, old_mapping=old_mapping,
                    new_expected=new_expected, new_mapping=new_mapping,
                    old_candidate_sha256=OLD_SHA, new_candidate_sha256=NEW_SHA,
                    new_stage=NEW_STAGE,
                    fail_at="new_active",
                )
            except RuntimeError as exc:
                if "after activating" not in str(exc):
                    raise
            else:
                raise RuntimeError("expected injected activation failure did not occur")
            if not (root / "app").is_dir() or not (root / ".plm-current-app-previous" / "app").is_dir():
                raise RuntimeError("injected failure did not retain active and previous app payloads")
            if _snapshot(root) != markers:
                raise RuntimeError("synthetic persistent markers changed during failed upgrade")
            restored = restore_prepared_payload(
                root, owner_token=token,
                old_expected=old_expected, old_mapping=old_mapping,
                new_expected=new_expected, new_mapping=new_mapping,
                old_candidate_sha256=OLD_SHA, new_candidate_sha256=NEW_SHA,
            )
            if restored.get("status") != "NON_RELEASE_CURRENT_APP_MANUAL_RESTORE_PASS":
                raise RuntimeError("explicit manual restore failed")
            if not (root / "app").is_dir() or not (root / ".plm-current-app-failed" / "app").is_dir():
                raise RuntimeError("manual restore did not preserve old and failed payload directories")
            if _snapshot(root) != markers:
                raise RuntimeError("synthetic persistent markers changed during manual restore")
            outcome = {"failure_injection": "new_active", "automatic_rollback": False,
                       "explicit_manual_restore": restored["status"],
                       "failed_new_payload_preserved": restored["failed_payload_preserved"],
                       "persistent_markers_unchanged": True}
        else:
            result = upgrade_validated_payload(
                root, next_root, owner_token=token,
                old_expected=old_expected, old_mapping=old_mapping,
                new_expected=new_expected, new_mapping=new_mapping,
                old_candidate_sha256=OLD_SHA, new_candidate_sha256=NEW_SHA,
                new_stage=NEW_STAGE,
            )
            if not (root / "app").is_dir() or not (root / ".plm-current-app-previous" / "app").is_dir():
                raise RuntimeError("upgrade did not retain active and previous app payloads")
            if _snapshot(root) != markers:
                raise RuntimeError("synthetic persistent markers changed during upgrade")
            outcome = {"upgrade_status": result["status"], "old_payload_retained": True,
                       "new_payload_active": True, "persistent_markers_unchanged": True}
        if candidate_stats != [(path.stat().st_size, path.stat().st_mtime_ns)
                               for path in (OLD_ZIP, NEW_ZIP)]:
            raise RuntimeError("candidate archive changed during rehearsal")
        return {"status": "PASS", "candidate_sha256": [OLD_SHA, NEW_SHA], **outcome}
    finally:
        _remove_owned(root, next_root, token,
                      root_created_by_this_run=root_created_by_this_run)


def main() -> int:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if not str(temp).isascii() or temp.drive.casefold() != Path("D:/").drive.casefold():
        raise RuntimeError("A14 requires the existing ASCII D: Temp volume")
    runs = [_one_run(temp, "failure", inject_failure=True)]
    print(json.dumps({"status": "PLT_PKG_01_A09_P51_A14_PASS_SCOPE_LIMITED",
                      "runs": runs, "release_eligible": False,
                      "database_started": False, "services_changed": False,
                      "formal_install_performed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
