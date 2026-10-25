from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from smoke_current_app_packaged_https import smoke  # noqa: E402

CANDIDATE_SHA256 = "3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455"
CANDIDATE = ROOT / "artifacts/package-prep/windows11/current-app-p51-a02-20261025/output/current-app-candidate-96313d4e1215/NOT-FOR-RELEASE-windows11-current-app.zip"
STAGE = Path(r"D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e")
ATTESTATION = CANDIDATE.parent / "verification-summary.json"


def run() -> dict[str, object]:
    temp = Path(os.environ.get("TEMP", "")).resolve(strict=True)
    if not str(temp).isascii() or temp.drive.casefold() != Path("D:/").drive.casefold():
        raise RuntimeError("A15 requires the established ASCII D: Temp volume")
    suffix = secrets.token_hex(12)
    pristine = temp / f"plm-install-rehearsal-a15p-{suffix}"
    target = temp / f"plm-install-rehearsal-a15t-{suffix}"
    if pristine.exists() or target.exists():
        raise RuntimeError("fresh isolated roots required")
    result = smoke(
        CANDIDATE, STAGE, pristine, target, CANDIDATE_SHA256,
        fast_reuse_verified_stage=True,
        prior_attestation=ATTESTATION,
    )
    expected = {
        "status": "SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS",
        "api_health_ready": 200,
        "api_health_live": 200,
        "https_health_ready": 200,
        "https_health_live": 200,
        "frontend_https_asset_count": 2,
        "login_status": 200,
        "session_status": 200,
        "unlicensed_project_status": 403,
        "packaged_python_process_started": True,
        "packaged_caddy_started": True,
        "temporary_pg18_started": True,
        "temporary_processes_stopped": True,
        "temporary_files_removed": True,
        "synthetic_vault_targets_absent": True,
        "fixed_candidate_unmodified": True,
        "release_eligible": False,
        "formal_trust_provisioned": False,
        "legal_clearance": False,
        "archive_sha256_reused_from_prior_attestation": True,
    }
    mismatches = {key: (result.get(key), value) for key, value in expected.items()
                  if result.get(key) != value}
    if mismatches:
        raise RuntimeError("A15 result contract mismatch: " + json.dumps(mismatches, sort_keys=True))
    if pristine.exists() or target.exists():
        raise RuntimeError("A15 owned installation roots remain after smoke")
    return {"status": "PLT_PKG_01_A09_P51_A15_PASS_SCOPE_LIMITED",
            "candidate_sha256": CANDIDATE_SHA256,
            "api_health_ready": result["api_health_ready"],
            "api_health_live": result["api_health_live"],
            "https_health_ready": result["https_health_ready"],
            "https_health_live": result["https_health_live"],
            "frontend_https_asset_count": result["frontend_https_asset_count"],
            "login_status": result["login_status"],
            "session_status": result["session_status"],
            "unlicensed_project_status": result["unlicensed_project_status"],
            "packaged_python_process_started": result["packaged_python_process_started"],
            "packaged_caddy_started": result["packaged_caddy_started"],
            "temporary_pg18_started": result["temporary_pg18_started"],
            "temporary_processes_stopped": result["temporary_processes_stopped"],
            "temporary_files_removed": result["temporary_files_removed"],
            "synthetic_vault_targets_absent": result["synthetic_vault_targets_absent"],
            "archive_sha256_reused_from_prior_attestation": True,
            "release_eligible": False, "formal_trust_provisioned": False,
            "legal_clearance": False}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
