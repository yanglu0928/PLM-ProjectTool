"""Isolated directory-layout upgrade/restore rehearsal for Current App candidates."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from plan_windows_unified_caddy_install import META, exact_mapping


def _stage_inventory(stage: Path) -> tuple[dict[str, str], dict[str, str]]:
    stage = stage.resolve(strict=True)
    if stage.parent != Path(tempfile.gettempdir()).resolve(strict=True) or not stage.name.startswith("plm-current-app-stage-"):
        raise ValueError("verified Current App stage must be a direct Temp child")
    hashes: dict[str, str] = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        sha, sep, name = line.partition("  ")
        if sep != "  " or len(sha) != 64 or name in hashes:
            raise ValueError("candidate stage checksum inventory rejected")
        int(sha, 16)
        hashes[name] = sha
    mapping, _ = exact_mapping([*hashes, *META])
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()
              and p.name not in {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}}
    if actual != set(hashes):
        raise ValueError("candidate stage inventory differs from checksum manifest")
    return hashes, mapping


def _install(stage: Path, root: Path, hashes: dict[str, str], mapping: dict[str, str]) -> None:
    for source, destination in mapping.items():
        target = root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        source_path = stage / source
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError("candidate source escaped the verified stage")
        os.link(source_path, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != (hashes.get(source) or
                                                               hashlib.sha256(source_path.read_bytes()).hexdigest()):
            raise ValueError("installed candidate file hash differs")


def _verify(root: Path, hashes: dict[str, str], mapping: dict[str, str],
            allowed_extras: set[str] | None = None) -> None:
    expected = {name.casefold() for name in mapping.values()}
    extras = {name.casefold() for name in (allowed_extras or set())}
    actual = {p.relative_to(root).as_posix().casefold() for p in root.rglob("*") if p.is_file()}
    if actual != expected | extras:
        raise ValueError("installed layout inventory differs")
    for source, relative in mapping.items():
        expected_sha = hashes.get(source)
        if expected_sha and hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected_sha:
            raise ValueError("installed layout file hash differs: " + relative)


def _markers(root: Path, token: str) -> dict[str, str]:
    result = {}
    for name in ("plugins", "data", "config", "license", "logs"):
        folder = root / name
        folder.mkdir(exist_ok=True)
        if name != "logs":
            marker = folder / ("a16-" + token + ".marker")
            marker.write_text("synthetic:" + name + ":" + token + "\n", encoding="ascii")
            result[marker.relative_to(root).as_posix()] = hashlib.sha256(marker.read_bytes()).hexdigest()
    return result


def rehearse_upgrade(old_stage: Path, new_stage: Path, target: Path,
                     *, fail_at: str | None = None) -> dict[str, object]:
    """Install old layout, switch runtime/app, preserve marker dirs, and return evidence.

    The target is owned and later removed by the enclosing HTTPS smoke. Previous
    runtime/app trees are kept in a sibling backup and must be explicitly cleaned.
    """
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    target = target.resolve()
    if target.parent != temp or not target.name.startswith("plm-install-rehearsal-a16t-") or target.exists() or target.is_symlink():
        raise ValueError("fresh A16-owned direct Temp target required")
    old_hashes, old_map = _stage_inventory(old_stage)
    new_hashes, new_map = _stage_inventory(new_stage)
    old_config = {name: old_hashes[name] for name, target_name in old_map.items()
                  if target_name.startswith("config/") and name in old_hashes}
    new_config = {name: new_hashes[name] for name, target_name in new_map.items()
                  if target_name.startswith("config/") and name in new_hashes}
    old_config_targets = {name: target_name for name, target_name in old_map.items()
                          if target_name.startswith("config/")}
    new_config_targets = {name: target_name for name, target_name in new_map.items()
                          if target_name.startswith("config/")}
    if old_config != new_config or old_config_targets != new_config_targets:
        raise ValueError("candidate configuration payload changed; A16 must not overwrite persistent config")
    token = target.name.removeprefix("plm-install-rehearsal-a16t-")
    if len(token) < 8 or any(ch not in "0123456789abcdef" for ch in token):
        raise ValueError("A16 owner token rejected")
    target.mkdir()
    backup = temp / ("plm-install-rehearsal-a16b-" + token)
    backup.mkdir()
    try:
        preserved = _markers(target, token)
        _install(old_stage, target, old_hashes, old_map)
        _verify(target, old_hashes, old_map, set(preserved))
        new_root = temp / ("plm-install-rehearsal-a16n-" + token)
        new_root.mkdir()
        try:
            _install(new_stage, new_root, new_hashes, new_map)
            # Keep persistent directories and their synthetic data untouched.
            for folder in ("runtime", "app"):
                os.rename(target / folder, backup / folder)
            for folder in ("runtime", "app"):
                os.rename(new_root / folder, target / folder)
            _verify(target, new_hashes, new_map, set(preserved))
            if fail_at == "new_active":
                raise RuntimeError("injected failure after new layout activation")
        finally:
            if new_root.exists():
                shutil.rmtree(new_root)
        after = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for folder in ("plugins", "data", "config", "license")
                 for p in (target / folder).rglob("*") if p.is_file() and p.name.startswith("a16-")}
        if after != preserved:
            raise ValueError("persistent synthetic markers changed during upgrade")
        return {"status": "A16_DIRECTORY_UPGRADE_PASS",
                "persistent_files": after, "persistent_file_count": len(after),
                "backup_root": str(backup), "backup_token": token,
                "candidate_file_count": len(new_map)}
    except BaseException:
        # Deliberately do not auto-restore. The caller must invoke restore_previous.
        raise


def restore_previous(target: Path, backup: Path) -> dict[str, object]:
    """Explicitly restore backed-up runtime/app and quarantine the failed version."""
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    target, backup = target.resolve(strict=True), backup.resolve(strict=True)
    if (target.parent != temp or not target.name.startswith("plm-install-rehearsal-a16t-")
            or backup.parent != temp or not backup.name.startswith("plm-install-rehearsal-a16b-")
            or target.is_symlink() or backup.is_symlink()):
        raise ValueError("A16 restore ownership boundary rejected")
    if target.name.removeprefix("plm-install-rehearsal-a16t-") != backup.name.removeprefix("plm-install-rehearsal-a16b-"):
        raise ValueError("A16 restore owner token mismatch")
    failed = temp / ("plm-install-rehearsal-a16f-" + uuid.uuid4().hex)
    failed.mkdir()
    for folder in ("runtime", "app"):
        if not (backup / folder).is_dir() or not (target / folder).is_dir():
            raise ValueError("A16 restore payload missing")
        os.rename(target / folder, failed / folder)
    for folder in ("runtime", "app"):
        os.rename(backup / folder, target / folder)
    return {"status": "A16_MANUAL_RESTORE_PASS", "failed_root": str(failed)}
