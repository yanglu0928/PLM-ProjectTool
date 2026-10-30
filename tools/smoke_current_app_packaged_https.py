"""Run current non-release app package behind synthetic HTTPS in disposable layout."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from install_windows_caddy_go_atomic_rehearsal import _copy_and_publish
from package_windows_current_app_candidate import PGVECTOR_WHEEL_SHA256
from package_windows_unified_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from rehearse_windows_unified_pg18_layout import validate_output_root
from smoke_packaged_platform_write_https import smoke as original_smoke
from verify_windows_unified_extract import verify as verify_stage

PARENT_ONLY_PAYLOAD_PATHS = frozenset({"payload/check-startup.ps1"})


def _app_projection_hashes(hashes: dict[str, str]) -> dict[str, str]:
    """Keep verified app files; omit only the parent-level startup diagnostic."""
    return {name: digest for name, digest in hashes.items()
            if name not in PARENT_ONLY_PAYLOAD_PATHS}



KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"


def _target_rehearsal(callback, default, candidate: Path, stage: Path,
                      layout: Path) -> dict[str, object]:
    evidence = (callback or default)(candidate, candidate, stage, layout)
    if not isinstance(evidence, dict):
        raise ValueError("target layout rehearsal must return evidence")
    return evidence


def _prior_archive_attestation(candidate: Path, expected_sha256: str,
                               attestation: Path) -> tuple[int, int]:
    try:
        summary = json.loads(attestation.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("prior candidate integrity attestation unavailable") from exc
    stat = candidate.stat()
    archive = str(summary.get("archive", "")).replace("\\", "/")
    suffix = "/".join(candidate.parts[-2:])
    if (summary.get("status") != "WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS"
            or summary.get("archive_sha256") != expected_sha256
            or summary.get("archive_bytes") != stat.st_size
            or not archive.endswith(suffix)
            or summary.get("release_eligible") is not False
            or summary.get("legal_clearance") is not False):
        raise ValueError("prior candidate integrity attestation mismatch")
    return stat.st_size, stat.st_mtime_ns


def _inputs(candidate: Path, stage: Path, expected_sha256: str) -> tuple[dict[str, str], dict[str, str], str, int]:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    resolved = stage.resolve(strict=True)
    if (resolved.parent != temp or not resolved.name.startswith("plm-current-app-stage-")
            or not str(resolved).isascii() or Path(r"C:\PLMTool").exists()
            or digest_path(candidate) != expected_sha256):
        raise ValueError("current candidate or stage identity rejected")
    checked = verify_stage(resolved, expected_kind=KIND)
    manifest = json.loads((resolved / "manifest.json").read_text(encoding="utf-8"))
    count = manifest.get("payload_file_count")
    if (type(count) is not int or checked["payload_file_count"] != count
            or manifest.get("pgvector_wheel_sha256") != PGVECTOR_WHEEL_SHA256
            or manifest.get("legal_clearance") is not False):
        raise ValueError("current candidate payload count differs")
    with zipfile.ZipFile(candidate) as archive:
        if any((resolved / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("current stage metadata differs from ZIP")
    hashes = {}
    for line in (resolved / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        sha, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("current stage hash manifest rejected")
        hashes[name] = sha
    app_hashes = _app_projection_hashes(hashes)
    projected_count = len(app_hashes)
    mapping, mapping_sha = exact_mapping([*app_hashes, *META])
    if (len(mapping) != projected_count + len(META) or
            mapping.get("payload/runtime/packages/plm_assistant/modules/evidence/api/lookup_eligibility_operation.py") !=
            "runtime/python/packages/plm_assistant/modules/evidence/api/lookup_eligibility_operation.py" or
            mapping.get("payload/runtime/packages/plm_assistant/migrations/versions/20261024_0185_outline_review_state_guard.py") !=
            "runtime/python/packages/plm_assistant/migrations/versions/20261024_0185_outline_review_state_guard.py" or
            mapping.get("payload/runtime/packages/pgvector/sqlalchemy/__init__.py") !=
            "runtime/python/packages/pgvector/sqlalchemy/__init__.py" or
            mapping.get("payload/runtime/packages/plm_assistant/modules/workflow/api/start_workflow.py") !=
            "runtime/python/packages/plm_assistant/modules/workflow/api/start_workflow.py"):
        raise ValueError("current app layout mapping differs")
    return hashes, mapping, mapping_sha, projected_count


def smoke(candidate: Path, stage: Path, pristine: Path, target: Path,
          expected_sha256: str, *, synthetic_license_document_factory=None,
          licensed_https_probe=None, fast_reuse_verified_stage: bool = False,
          prior_attestation: Path | None = None,
          target_layout_rehearser=None) -> dict[str, object]:
    validate_output_root(pristine)
    validate_output_root(target)
    if pristine == target or stage in {pristine, target}:
        raise ValueError("stage and synthetic layouts must differ")
    archive_stat: tuple[int, int] | None = None
    if fast_reuse_verified_stage:
        # Reuse the exact stage already byte-verified by P51-A02; retain archive
        # identity and complete file-name checks without rereading all payload bytes.
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        resolved = stage.resolve(strict=True)
        archive_stat = (_prior_archive_attestation(candidate, expected_sha256, prior_attestation)
                        if prior_attestation is not None else None)
        if (resolved.parent != temp or not resolved.name.startswith("plm-current-app-stage-")
                or not str(resolved).isascii() or Path(r"C:\PLMTool").exists()
                or (archive_stat is None and digest_path(candidate) != expected_sha256)):
            raise ValueError("current candidate or stage identity rejected")
        manifest = json.loads((resolved / "manifest.json").read_text(encoding="utf-8"))
        if (manifest.get("kind") != KIND or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False):
            raise ValueError("current stage is not the expected non-release candidate")
        hashes = {}
        for line in (resolved / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
            sha, separator, name = line.partition("  ")
            if separator != "  " or len(sha) != 64 or name in hashes:
                raise ValueError("current stage hash manifest rejected")
            hashes[name] = sha
        count = manifest.get("payload_file_count")
        if type(count) is not int or count != len(hashes):
            raise ValueError("current stage manifest count differs")
        actual = {p.relative_to(resolved).as_posix() for p in resolved.rglob("*")
                  if p.is_file() and p.name not in {"manifest.json", "payload-sha256sums.txt",
                                                    "third-party-inventory.json"}}
        links = [p.relative_to(resolved).as_posix() for p in resolved.rglob("*")
                 if p.is_symlink()]
        if actual != set(hashes) or links:
            raise ValueError(
                "current stage inventory or link boundary differs "
                f"(missing={len(set(hashes) - actual)}, extra={len(actual - set(hashes))}, "
                f"links={len(links)})"
            )
        app_hashes = _app_projection_hashes(hashes)
        projected_count = len(app_hashes)
        mapping, mapping_sha = exact_mapping([*app_hashes, *META])
        if len(mapping) != projected_count + len(META):
            raise ValueError("current app layout mapping count differs")
        count = projected_count
    else:
        hashes, mapping, mapping_sha, count = _inputs(candidate, stage, expected_sha256)

    def check_layout(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict:
        if (_candidate != candidate or _source != candidate or _stage != stage or
                layout.resolve(strict=True).parent != Path(tempfile.gettempdir()).resolve(strict=True)):
            raise ValueError("current layout source differs")
        persistent = (target_layout_evidence or {}).get("persistent_files", {})
        if not isinstance(persistent, dict):
            raise ValueError("persistent layout evidence rejected")
        landed = {path.relative_to(layout).as_posix().casefold()
                  for path in layout.rglob("*") if path.is_file()}
        expected_files = {name.casefold() for name in mapping.values()} | {
            str(name).casefold() for name in persistent
        }
        if landed != expected_files:
            raise ValueError("current layout file inventory differs")
        for relative, expected_sha in persistent.items():
            if digest_path(layout / Path(relative)) != expected_sha:
                raise ValueError("persistent layout marker differs: " + str(relative))
        if not fast_reuse_verified_stage:
            for source, destination in mapping.items():
                expected = hashes[source] if source in hashes else digest_path(stage / source)
                if digest_path(layout / destination) != expected:
                    raise ValueError("current layout hash differs: " + destination)
        # Keep the smoke's package-file count comparable to its pristine verifier;
        # persistent marker files are independently hash-checked above and reported
        # by the A16 rehearsal evidence, not counted as candidate payload.
        return {"mapping_sha256": mapping_sha, "file_count": len(mapping)}

    def place_layout(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict:
        if (_candidate != candidate or _source != candidate or _stage != stage):
            raise ValueError("current layout placement source differs")
        if fast_reuse_verified_stage:
            validate_output_root(layout)
            if layout.exists() or layout.is_symlink():
                raise ValueError("fresh hardlink overlay target already exists")
            layout.mkdir()
            try:
                for source, destination in mapping.items():
                    source_path, target_path = stage / source, layout / destination
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    os.link(source_path, target_path)
                for name in ("plugins", "data", "logs", "license"):
                    (layout / name).mkdir(exist_ok=False)
                return {"status": "VERIFIED_STAGE_HARDLINK_OVERLAY_PASS",
                        "target_file_count": len(mapping)}
            except BaseException:
                if layout.exists() and not layout.is_symlink():
                    shutil.rmtree(layout)
                raise
        result = _copy_and_publish(stage, layout, mapping, hashes)
        if result.get("target_file_count") != len(mapping):
            raise ValueError("current layout count differs")
        return result

    target_layout_evidence: dict[str, object] | None = None

    def rehearse_target(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict:
        nonlocal target_layout_evidence
        evidence = _target_rehearsal(target_layout_rehearser, place_layout,
                                     _candidate, _stage, layout)
        target_layout_evidence = evidence
        return evidence

    place_layout(candidate, candidate, stage, pristine)
    try:
        result = original_smoke(candidate, candidate, stage, pristine, target,
                                layout_verifier=check_layout,
                                layout_rehearser=rehearse_target,
                                synthetic_license_document_factory=synthetic_license_document_factory,
                                licensed_https_probe=licensed_https_probe)
        if (result.get("synthetic_layout_file_count_before_injection") != count + len(META)
                or result.get("fixed_candidate_unmodified") is not True
                or result.get("synthetic_vault_targets_absent") is not True
                or result.get("temporary_processes_stopped") is not True
                or result.get("release_eligible") is not False):
            raise ValueError("current packaged HTTPS smoke boundary differs")
        if (archive_stat is not None
                and archive_stat != (candidate.stat().st_size, candidate.stat().st_mtime_ns)):
            raise ValueError("candidate archive changed during smoke")
        if archive_stat is None and digest_path(candidate) != expected_sha256:
            raise ValueError("current candidate changed during smoke")
        return {**result, "status": "SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS",
                "candidate_sha256": expected_sha256, "legal_clearance": False,
                "target_layout_evidence": target_layout_evidence,
                "archive_sha256_reused_from_prior_attestation": archive_stat is not None}
    finally:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if pristine.exists():
            resolved = pristine.resolve(strict=True)
            if (resolved.parent != temp or not resolved.name.startswith("plm-install-rehearsal-")
                    or resolved.is_symlink()):
                raise RuntimeError("pristine cleanup scope rejected")
            shutil.rmtree(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.stage, args.pristine, args.target,
                           args.expected_sha256), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
