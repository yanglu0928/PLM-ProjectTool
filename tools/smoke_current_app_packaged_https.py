"""Run current non-release app package behind synthetic HTTPS in disposable layout."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from install_windows_caddy_go_atomic_rehearsal import _copy_and_publish
from package_windows_unified_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from rehearse_windows_unified_pg18_layout import validate_output_root
from smoke_packaged_platform_write_https import smoke as original_smoke
from verify_windows_unified_extract import verify as verify_stage


KIND = "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE"
COUNT = 21182


def _inputs(candidate: Path, stage: Path, expected_sha256: str) -> tuple[dict[str, str], dict[str, str], str]:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    resolved = stage.resolve(strict=True)
    if (resolved.parent != temp or not resolved.name.startswith("plm-current-app-stage-")
            or not str(resolved).isascii() or Path(r"C:\PLMTool").exists()
            or digest_path(candidate) != expected_sha256):
        raise ValueError("current candidate or stage identity rejected")
    checked = verify_stage(resolved, expected_kind=KIND)
    if checked["payload_file_count"] != COUNT:
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
    mapping, mapping_sha = exact_mapping([*hashes, *META])
    if (len(mapping) != COUNT + len(META) or
            mapping.get("payload/runtime/packages/plm_assistant/modules/evidence/api/lookup_eligibility_operation.py") !=
            "runtime/python/packages/plm_assistant/modules/evidence/api/lookup_eligibility_operation.py" or
            mapping.get("payload/runtime/packages/plm_assistant/migrations/versions/20261001_0052_evidence_parse_provenance.py") !=
            "runtime/python/packages/plm_assistant/migrations/versions/20261001_0052_evidence_parse_provenance.py" or
            mapping.get("payload/runtime/packages/plm_assistant/modules/workflow/api/start_workflow.py") !=
            "runtime/python/packages/plm_assistant/modules/workflow/api/start_workflow.py"):
        raise ValueError("current app layout mapping differs")
    return hashes, mapping, mapping_sha


def smoke(candidate: Path, stage: Path, pristine: Path, target: Path,
          expected_sha256: str, *, synthetic_license_document_factory=None,
          licensed_https_probe=None) -> dict[str, object]:
    validate_output_root(pristine)
    validate_output_root(target)
    if pristine == target or stage in {pristine, target}:
        raise ValueError("stage and synthetic layouts must differ")
    hashes, mapping, mapping_sha = _inputs(candidate, stage, expected_sha256)

    def check_layout(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict:
        if (_candidate != candidate or _source != candidate or _stage != stage or
                layout.resolve(strict=True).parent != Path(tempfile.gettempdir()).resolve(strict=True)):
            raise ValueError("current layout source differs")
        landed = {path.relative_to(layout).as_posix().casefold()
                  for path in layout.rglob("*") if path.is_file()}
        if landed != {name.casefold() for name in mapping.values()}:
            raise ValueError("current layout file inventory differs")
        for source, destination in mapping.items():
            expected = hashes[source] if source in hashes else digest_path(stage / source)
            if digest_path(layout / destination) != expected:
                raise ValueError("current layout hash differs: " + destination)
        return {"mapping_sha256": mapping_sha, "file_count": len(mapping)}

    def place_layout(_candidate: Path, _source: Path, _stage: Path, layout: Path) -> dict:
        if (_candidate != candidate or _source != candidate or _stage != stage):
            raise ValueError("current layout placement source differs")
        result = _copy_and_publish(stage, layout, mapping, hashes)
        if result.get("target_file_count") != len(mapping):
            raise ValueError("current layout count differs")
        return result

    place_layout(candidate, candidate, stage, pristine)
    try:
        result = original_smoke(candidate, candidate, stage, pristine, target,
                                layout_verifier=check_layout,
                                layout_rehearser=place_layout,
                                synthetic_license_document_factory=synthetic_license_document_factory,
                                licensed_https_probe=licensed_https_probe)
        if (result.get("synthetic_layout_file_count_before_injection") != COUNT + len(META)
                or result.get("fixed_candidate_unmodified") is not True
                or result.get("synthetic_vault_targets_absent") is not True
                or result.get("temporary_processes_stopped") is not True
                or result.get("release_eligible") is not False):
            raise ValueError("current packaged HTTPS smoke boundary differs")
        if digest_path(candidate) != expected_sha256:
            raise ValueError("current candidate changed during smoke")
        return {**result, "status": "SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS",
                "candidate_sha256": expected_sha256, "legal_clearance": False}
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
