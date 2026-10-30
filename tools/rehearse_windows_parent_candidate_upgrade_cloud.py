"""Rehearse a reversible parent-package replacement on hosted Windows temp only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from stage_windows_parent_candidate_cloud import stage_candidate


OLD_ARTIFACT_RUN = "40995913354"
PERSISTENT_DIRS = ("data", "config", "license", "plugins")
PACKAGE_METADATA = ("manifest.json", "payload-sha256sums.txt")
PACKAGE_CONTENTS = ("payload", "provenance", *PACKAGE_METADATA)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _runner_temp() -> Path:
    configured = os.environ.get("RUNNER_TEMP")
    if not configured:
        raise ValueError("GitHub RUNNER_TEMP is required")
    root = Path(configured).resolve(strict=True)
    if (not str(root).isascii() or root.drive.casefold() != "d:"
            or Path(tempfile.gettempdir()).resolve(strict=True) != root):
        raise ValueError("A34 requires ASCII D: RUNNER_TEMP for all temp operations")
    return root


def _owned_child(path: Path, temp: Path, prefix: str, *, fresh: bool) -> Path:
    try:
        parent = path.parent.resolve(strict=True)
    except OSError:
        raise ValueError("A34 runner-temp ownership boundary rejected") from None
    if (parent != temp or path.drive.casefold() == "c:"
            or not str(path).isascii() or not path.name.startswith(prefix)
            or path.is_symlink() or (fresh and path.exists())):
        raise ValueError("A34 runner-temp ownership boundary rejected")
    return path


def _read_checksums(stage: Path) -> dict[str, str]:
    sums = stage / "payload-sha256sums.txt"
    result: dict[str, str] = {}
    for line in sums.read_text(encoding="ascii").splitlines():
        digest, separator, name = line.partition("  ")
        pure = PurePosixPath(name)
        if (separator != "  " or len(digest) != 64 or name in result
                or not name.startswith(("payload/", "provenance/"))
                or "\\" in name or ":" in name
                or pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts)):
            raise ValueError("A34 candidate checksum inventory rejected")
        int(digest, 16)
        result[name] = digest
    if not result:
        raise ValueError("A34 candidate payload is empty")
    actual = {
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if (path.is_file() and not path.is_symlink()
            and path.relative_to(stage).as_posix() not in
            (*PACKAGE_METADATA, "candidate-staging-receipt.json"))
    }
    if actual != set(result):
        raise ValueError("A34 staged payload inventory differs from its checksums")
    for name, expected in result.items():
        if _sha_file(stage.joinpath(*PurePosixPath(name).parts)) != expected:
            raise ValueError("A34 staged payload hash changed: " + name)
    return result


def _metadata(stage: Path) -> dict[str, object]:
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8-sig"))
    if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
            or manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False):
        raise ValueError("A34 requires a verified non-release parent candidate")
    return manifest


def _link_candidate(stage: Path, destination: Path, hashes: dict[str, str]) -> None:
    destination.mkdir(exist_ok=True)
    for name in ("payload", "provenance"):
        (destination / name).mkdir(exist_ok=True)
    for name in sorted(hashes):
        source = stage.joinpath(*PurePosixPath(name).parts)
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink() or not source.is_file():
            raise ValueError("A34 source payload escaped the verified stage")
        os.link(source, target)
        if _sha_file(target) != hashes[name]:
            raise ValueError("A34 installed payload hash differs: " + name)
    for name in PACKAGE_METADATA:
        source = stage / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("A34 package metadata is missing")
        os.link(source, destination / name)


def _install_initial(stage: Path, target: Path, hashes: dict[str, str]) -> None:
    target.mkdir()
    for name in PERSISTENT_DIRS + ("logs",):
        (target / name).mkdir()
    for name in PERSISTENT_DIRS:
        marker = target / name / ("a34-" + target.name.rsplit("-", 1)[-1] + ".marker")
        marker.write_text("synthetic:" + name + "\n", encoding="ascii")
    _link_candidate(stage, target, hashes)


def _marker_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha_file(path)
        for folder in PERSISTENT_DIRS
        for path in sorted((root / folder).glob("a34-*.marker"))
    }


def _verify_candidate(stage: Path, root: Path, hashes: dict[str, str]) -> None:
    actual = {
        path.relative_to(root).as_posix()
        for name in ("payload", "provenance")
        for path in (root / name).rglob("*")
        if path.is_file()
    }
    if actual != set(hashes):
        raise ValueError("A34 installed candidate inventory differs")
    for name, expected in hashes.items():
        target = root.joinpath(*PurePosixPath(name).parts)
        if target.is_symlink() or not target.is_file() or _sha_file(target) != expected:
            raise ValueError("A34 installed candidate verification failed: " + name)
    for name in PACKAGE_METADATA:
        source_bytes = (stage / name).read_bytes()
        if (root / name).is_symlink() or (root / name).read_bytes() != source_bytes:
            raise ValueError("A34 installed candidate metadata differs: " + name)


def _activate(stage: Path, target: Path, backup: Path,
              hashes: dict[str, str]) -> None:
    backup.mkdir()
    for name in PACKAGE_CONTENTS:
        os.replace(target / name, backup / name)
    replacement = backup.parent / ("plm-a34-next-" + backup.name.rsplit("-", 1)[-1])
    try:
        _link_candidate(stage, replacement, hashes)
        for name in PACKAGE_CONTENTS:
            os.replace(replacement / name, target / name)
    finally:
        if replacement.exists():
            shutil.rmtree(replacement)


def _manual_restore(target: Path, backup: Path, failed: Path) -> None:
    failed.mkdir()
    for name in PACKAGE_CONTENTS:
        if not (target / name).exists() or not (backup / name).exists():
            raise ValueError("A34 manual restore payload is incomplete")
        os.replace(target / name, failed / name)
    for name in PACKAGE_CONTENTS:
        os.replace(backup / name, target / name)


def _run_launcher(root: Path, blockers: set[str]) -> dict[str, object]:
    script = root / "payload" / "start-trial.ps1"
    if script.is_symlink() or not script.is_file():
        raise ValueError("A34 upgraded candidate launcher is missing")
    shell = shutil.which("powershell")
    if os.name != "nt" or not shell:
        raise ValueError("A34 requires hosted Windows PowerShell 5.1")
    environment = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("PLM_")
    }
    environment.pop("PYTHONPATH", None)
    environment["PLM_STARTUP_DIAGNOSTIC_TRACE"] = "A34"
    result = subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
         "Bypass", "-File", str(script)],
        cwd=root, capture_output=True, text=True, errors="replace",
        timeout=30, env=environment,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError(
            "A34 upgraded launcher did not emit a JSON diagnostic; stdout="
            + repr(result.stdout) + "; stderr=" + repr(result.stderr)
        ) from None
    if (result.returncode != 1 or report.get("status") != "BLOCKED"
            or result.stderr.strip() !=
            "Packaged startup blocked; see BLOCKED diagnostics above."
            or report.get("release_eligible") is not False
            or report.get("legal_clearance") is not False
            or set(report.get("blocker_codes", [])) != blockers
            or "sensitive-path-marker" in result.stdout):
        raise ValueError("A34 upgraded launcher did not retain the A33 fail-closed contract")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
    return {"status": "BLOCKED", "exit_code": result.returncode,
            "blocker_codes": sorted(blockers), "listener_started": False,
            "service_started": False, "product_api_started": False}


def _cleanup(path: Path | None, temp: Path, prefix: str) -> None:
    if path is None or not path.exists():
        return
    resolved = _owned_child(path, temp, prefix, fresh=False).resolve(strict=True)
    if resolved.parent != temp or resolved.is_symlink() or not resolved.is_dir():
        raise RuntimeError("A34 refused cleanup outside its owned runner-temp root")
    shutil.rmtree(resolved)


def run(old_archive: Path, old_summary: Path, current_archive: Path,
        current_summary: Path, work_root: Path,
        *, old_run_id: str = OLD_ARTIFACT_RUN) -> dict[str, object]:
    if os.name != "nt":
        raise ValueError("A34 is a hosted Windows-only rehearsal")
    temp = _runner_temp()
    work_root = _owned_child(work_root, temp, "plm-a34-run-", fresh=True)
    token = secrets.token_hex(12)
    paths = {
        "old_stage": temp / ("plm-a34-old-stage-" + token),
        "new_stage": temp / ("plm-a34-new-stage-" + token),
        "target": work_root,
        "backup": temp / ("plm-a34-backup-" + token),
        "failed": temp / ("plm-a34-failed-" + token),
    }
    for key, path in paths.items():
        prefix = "plm-a34-run-" if key == "target" else "plm-a34-" + key.replace("_", "-") + "-"
        _owned_child(path, temp, prefix, fresh=True)

    stages: list[Path] = []
    try:
        old_receipt = stage_candidate(old_archive, old_summary, paths["old_stage"])
        stages.append(paths["old_stage"])
        current_receipt = stage_candidate(current_archive, current_summary, paths["new_stage"])
        stages.append(paths["new_stage"])
        old_meta, current_meta = _metadata(paths["old_stage"]), _metadata(paths["new_stage"])
        if str(old_meta.get("workflow_run")) != old_run_id:
            raise ValueError("A34 prior candidate run identity differs")
        if str(current_meta.get("workflow_run")) != os.environ.get("GITHUB_RUN_ID"):
            raise ValueError("A34 current candidate is not from this workflow run")
        old_hashes = _read_checksums(paths["old_stage"])
        current_hashes = _read_checksums(paths["new_stage"])
        _install_initial(paths["old_stage"], work_root, old_hashes)
        before_markers = _marker_hashes(work_root)
        if len(before_markers) != len(PERSISTENT_DIRS):
            raise ValueError("A34 persistent marker fixture is incomplete")
        _verify_candidate(paths["old_stage"], work_root, old_hashes)

        try:
            _activate(paths["new_stage"], work_root, paths["backup"], current_hashes)
            _verify_candidate(paths["new_stage"], work_root, current_hashes)
            if _marker_hashes(work_root) != before_markers:
                raise ValueError("A34 replacement changed persistent markers")
            raise RuntimeError("A34 injected failure after current package activation")
        except RuntimeError as exc:
            if "A34 injected failure" not in str(exc):
                raise
        _verify_candidate(paths["new_stage"], work_root, current_hashes)
        if (work_root / "manifest.json").read_bytes() != (
                paths["new_stage"] / "manifest.json").read_bytes():
            raise ValueError("A34 injected failure unexpectedly restored the old package")

        failed = _owned_child(paths["failed"], temp, "plm-a34-failed-", fresh=True)
        _manual_restore(work_root, paths["backup"], failed)
        _verify_candidate(paths["old_stage"], work_root, old_hashes)
        if _marker_hashes(work_root) != before_markers:
            raise ValueError("A34 manual restore changed persistent markers")

        # Re-activate the current candidate for the final fail-closed launcher check.
        second_backup = temp / ("plm-a34-final-backup-" + token)
        _owned_child(second_backup, temp, "plm-a34-final-backup-", fresh=True)
        _activate(paths["new_stage"], work_root, second_backup, current_hashes)
        _verify_candidate(paths["new_stage"], work_root, current_hashes)
        launcher = _run_launcher(work_root, set(current_meta["startup_preflight"]["blocker_codes"])
                                 | {"NON_RELEASE_CANDIDATE"})
        if _marker_hashes(work_root) != before_markers:
            raise ValueError("A34 launcher altered persistent markers")
        return {
            "status": "PLT_PKG_01_A09_P51_A34_PASS_LIMITED",
            "old_candidate_sha256": old_receipt["archive_sha256"],
            "old_candidate_source_commit": old_meta["source_commit"],
            "old_candidate_workflow_run": old_meta["workflow_run"],
            "current_candidate_sha256": current_receipt["archive_sha256"],
            "current_candidate_source_commit": current_meta["source_commit"],
            "current_candidate_workflow_run": current_meta["workflow_run"],
            "old_payload_file_count": len(old_hashes),
            "current_payload_file_count": len(current_hashes),
            "persistent_marker_count": len(before_markers),
            "persistent_markers_preserved": True,
            "automatic_rollback_performed": False,
            "new_candidate_remained_active_until_manual_restore": True,
            "explicit_manual_restore_passed": True,
            "failed_candidate_quarantined": all((failed / name).exists()
                                                 for name in PACKAGE_CONTENTS),
            "provenance_preserved_in_quarantine": any(
                (failed / "provenance").rglob("*")
            ),
            "launcher_after_upgrade": launcher,
            "services_started": False,
            "release_eligible": False,
            "legal_clearance": False,
            "execution_root_drive": work_root.drive,
        }
    finally:
        # If testing fails after creating the temporary backup/failure roots, clean only
        # paths whose direct parent and task-specific token were established above.
        _cleanup(paths["target"], temp, "plm-a34-run-")
        for path, prefix in (
            (paths["backup"], "plm-a34-backup-"),
            (paths["failed"], "plm-a34-failed-"),
            (temp / ("plm-a34-final-backup-" + token), "plm-a34-final-backup-"),
            (temp / ("plm-a34-next-" + token), "plm-a34-next-"),
        ):
            if path.name.endswith(token):
                _cleanup(path, temp, prefix)
        for stage in stages:
            _cleanup(stage, temp, "plm-a34-" + ("old-stage-" if stage == paths["old_stage"]
                                                  else "new-stage-"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-archive", required=True, type=Path)
    parser.add_argument("--old-summary", required=True, type=Path)
    parser.add_argument("--current-archive", required=True, type=Path)
    parser.add_argument("--current-summary", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.old_archive, args.old_summary, args.current_archive,
                         args.current_summary, args.work_root), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
