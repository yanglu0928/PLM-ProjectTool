from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from install_windows_current_app_candidate_rehearsal import candidate_inventory  # noqa: E402
from package_windows_unified_candidate import digest_path  # noqa: E402
from rehearse_current_app_directory_upgrade import (  # noqa: E402
    _stage_inventory,
    _verify,
    rehearse_upgrade,
    restore_previous,
)
from smoke_current_app_packaged_https import smoke  # noqa: E402

OLD_SHA = "4f090636986c5c2173a5fde48eb161a94e5ee285ce73a8deb529c8682e048f46"
NEW_SHA = "3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455"
OLD_ZIP = ROOT / "artifacts/package-prep/windows11/current-app-sur-a08-20261025/current-app-candidate-4eaa7f158bed/NOT-FOR-RELEASE-windows11-current-app.zip"
NEW_ZIP = ROOT / "artifacts/package-prep/windows11/current-app-p51-a02-20261025/output/current-app-candidate-96313d4e1215/NOT-FOR-RELEASE-windows11-current-app.zip"
OLD_ATTEST = OLD_ZIP.parent / "verification-summary.json"
NEW_ATTEST = NEW_ZIP.parent / "verification-summary.json"
OLD_STAGE = Path(r"D:\PLMToolTemp\plm-current-app-stage-sura08-fixed")
NEW_STAGE = Path(r"D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e")


def _cleanup(path: Path, prefix: str) -> None:
    if not path.exists():
        return
    temp = Path(tempfile_dir()).resolve(strict=True)
    resolved = path.resolve(strict=True)
    if (resolved.parent != temp or not resolved.name.startswith(prefix)
            or resolved.is_symlink() or not resolved.is_dir()):
        raise RuntimeError("A16 cleanup ownership check failed: " + path.name)
    shutil.rmtree(resolved)


def _verify_stage_metadata(candidate: Path, stage: Path) -> None:
    with zipfile.ZipFile(candidate) as archive:
        for name in ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"):
            if (stage / name).read_bytes() != archive.read(name):
                raise RuntimeError("candidate stage metadata differs: " + name)


def tempfile_dir() -> str:
    import tempfile
    return tempfile.gettempdir()


def _failure_restore(temp: Path, suffix: str) -> dict[str, object]:
    target = temp / ("plm-install-rehearsal-a16t-" + suffix)
    backup = temp / ("plm-install-rehearsal-a16b-" + suffix)
    old_hashes, old_map = _stage_inventory(OLD_STAGE)
    new_hashes, new_map = _stage_inventory(NEW_STAGE)
    try:
        try:
            rehearse_upgrade(OLD_STAGE, NEW_STAGE, target, fail_at="new_active")
            raise RuntimeError("A16 failure injection unexpectedly succeeded")
        except RuntimeError as exc:
            if "injected failure" not in str(exc):
                raise
        # The failed new layout must remain active until explicit operator restore.
        persistent = {p.relative_to(target).as_posix() for folder in ("plugins", "data", "config", "license")
                      for p in (target / folder).glob("a16-*.marker")}
        _verify(target, new_hashes, new_map, persistent)
        restored = restore_previous(target, backup)
        _verify(target, old_hashes, old_map, persistent)
        failed = Path(str(restored["failed_root"]))
        if not failed.is_dir():
            raise RuntimeError("failed candidate was not quarantined")
        _cleanup(failed, "plm-install-rehearsal-a16f-")
        return {"status": restored["status"], "automatic_rollback_performed": False,
                "failed_candidate_quarantined": True}
    finally:
        _cleanup(target, "plm-install-rehearsal-a16t-")
        _cleanup(backup, "plm-install-rehearsal-a16b-")


def run() -> dict[str, object]:
    if sys.platform != "win32" or Path(r"C:\PLMTool").exists():
        raise RuntimeError("A16 requires Windows 11 isolated Temp; formal root is prohibited")
    temp = Path(os.environ.get("TEMP", "")).resolve(strict=True)
    if not str(temp).isascii() or temp.drive.casefold() != Path("D:/").drive.casefold():
        raise RuntimeError("A16 requires the established ASCII D: Temp volume")
    old_expected, _ = candidate_inventory(OLD_ZIP, OLD_SHA, prior_attestation=OLD_ATTEST)
    new_expected, _ = candidate_inventory(NEW_ZIP, NEW_SHA, prior_attestation=NEW_ATTEST)
    old_archive_stat = (OLD_ZIP.stat().st_size, OLD_ZIP.stat().st_mtime_ns)
    old_stage_hashes, _ = _stage_inventory(OLD_STAGE)
    new_stage_hashes, _ = _stage_inventory(NEW_STAGE)
    if old_stage_hashes != old_expected or new_stage_hashes != new_expected:
        raise RuntimeError("candidate and verified stage inventories differ")
    _verify_stage_metadata(OLD_ZIP, OLD_STAGE)
    _verify_stage_metadata(NEW_ZIP, NEW_STAGE)
    suffix = secrets.token_hex(12)
    pristine = temp / f"plm-install-rehearsal-a16p-{suffix}"
    target = temp / f"plm-install-rehearsal-a16t-{suffix}"
    if pristine.exists() or target.exists():
        raise RuntimeError("fresh isolated A16 roots required")
    failure = _failure_restore(temp, secrets.token_hex(12))
    backup: Path | None = None
    callback_backups: list[Path] = []

    def upgrade_target(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict[str, object]:
        suffix = layout.name.removeprefix("plm-install-rehearsal-a16t-")
        callback_backups.append(temp / ("plm-install-rehearsal-a16b-" + suffix))
        return rehearse_upgrade(OLD_STAGE, NEW_STAGE, layout)

    try:
        result = smoke(
            NEW_ZIP, NEW_STAGE, pristine, target, NEW_SHA,
            fast_reuse_verified_stage=True, prior_attestation=NEW_ATTEST,
            target_layout_rehearser=upgrade_target,
        )
        evidence = result.get("target_layout_evidence")
        if not isinstance(evidence, dict) or evidence.get("status") != "A16_DIRECTORY_UPGRADE_PASS":
            raise RuntimeError("A16 upgraded target layout evidence missing")
        if evidence.get("persistent_file_count") != 4:
            raise RuntimeError("A16 persistent marker set incomplete")
        backup = Path(str(evidence["backup_root"]))
        if (result.get("api_health_ready") != 200 or result.get("api_health_live") != 200
                or result.get("https_health_ready") != 200 or result.get("https_health_live") != 200
                or result.get("frontend_https_asset_count") != 2
                or result.get("login_status") != 200 or result.get("session_status") != 200
                or result.get("unlicensed_project_status") != 403
                or result.get("temporary_processes_stopped") is not True
                or result.get("temporary_files_removed") is not True
                or result.get("synthetic_vault_targets_absent") is not True
                or result.get("fixed_candidate_unmodified") is not True
                or result.get("release_eligible") is not False):
            raise RuntimeError("A16 post-upgrade packaged health contract failed")
        if old_archive_stat != (OLD_ZIP.stat().st_size, OLD_ZIP.stat().st_mtime_ns):
            raise RuntimeError("old candidate archive changed during A16")
        return {
            "status": "PLT_PKG_01_A09_P51_A16_PASS_SCOPE_LIMITED",
            "old_candidate_sha256": OLD_SHA, "new_candidate_sha256": NEW_SHA,
            "same_target_directory_upgraded_then_started": True,
            "directory_upgrade": evidence,
            "manual_failure_restore": failure,
            "api_health_ready": result["api_health_ready"],
            "api_health_live": result["api_health_live"],
            "https_health_ready": result["https_health_ready"],
            "https_health_live": result["https_health_live"],
            "frontend_https_asset_count": result["frontend_https_asset_count"],
            "login_status": result["login_status"],
            "session_status": result["session_status"],
            "unlicensed_project_status": result["unlicensed_project_status"],
            "temporary_processes_stopped": result["temporary_processes_stopped"],
            "archive_sha256_reused_from_prior_attestation": True,
            "formal_trust_provisioned": False, "legal_clearance": False,
            "release_eligible": False,
        }
    finally:
        if backup is not None:
            _cleanup(backup, "plm-install-rehearsal-a16b-")
        for orphan in callback_backups:
            _cleanup(orphan, "plm-install-rehearsal-a16b-")
        _cleanup(pristine, "plm-install-rehearsal-a16p-")
        _cleanup(target, "plm-install-rehearsal-a16t-")


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
