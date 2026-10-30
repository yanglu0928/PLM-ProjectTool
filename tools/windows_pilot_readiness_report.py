"""Combine non-secret Pilot references and package preflight claims into a non-authorizing report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_windows_pilot_input_register import DATABASE_CREDENTIAL_TARGET, validate_register


EXPECTED_STARTUP_FIELDS = {
    "blocker_codes",
    "database_credential_reference_verified",
    "database_credential_target_reference",
    "formal_license_trust_verified",
    "formal_startup_ready",
    "packaged_product_public_key_resource_present",
    "service_identity_acl_verified",
    "tls_certificate_configured",
    "tls_private_key_configured",
}
FIELD_BLOCKERS = {
    "packaged_product_public_key_resource_present": "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
    "formal_license_trust_verified": "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
    "database_credential_reference_verified": "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
    "service_identity_acl_verified": "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
}


def _manifest_blockers(manifest: Any) -> tuple[bool, list[str]]:
    if not isinstance(manifest, dict):
        return False, []
    startup = manifest.get("startup_preflight")
    if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
            or manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False
            or not isinstance(startup, dict)
            or set(startup) != EXPECTED_STARTUP_FIELDS
            or startup.get("database_credential_target_reference") != DATABASE_CREDENTIAL_TARGET
            or not isinstance(startup.get("blocker_codes"), list)
            or any(type(startup.get(key)) is not bool for key in (
                "database_credential_reference_verified", "formal_license_trust_verified",
                "formal_startup_ready", "packaged_product_public_key_resource_present",
                "service_identity_acl_verified", "tls_certificate_configured",
                "tls_private_key_configured",
            ))):
        return False, []

    codes = [code for key, code in FIELD_BLOCKERS.items() if startup[key] is not True]
    if startup["tls_certificate_configured"] is not True or startup["tls_private_key_configured"] is not True:
        codes.append("TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED")
    codes = sorted(set(codes))
    declared = startup["blocker_codes"]
    if (any(not isinstance(code, str) for code in declared)
            or sorted(declared) != codes
            or startup["formal_startup_ready"] is not (not codes)):
        return False, []
    return True, codes


def build_report(manifest: Any, register: Any) -> dict[str, Any]:
    manifest_valid, startup_codes = _manifest_blockers(manifest)
    register_result = validate_register(register)
    reason_codes = {"NON_RELEASE_CANDIDATE"}
    if not manifest_valid:
        reason_codes.add("PACKAGE_MANIFEST_INVALID")
    else:
        reason_codes.update(startup_codes)
    if register_result["status"] == "INVALID":
        reason_codes.add("INPUT_REGISTER_INVALID")
    elif register_result["status"] == "INCOMPLETE":
        reason_codes.add("INPUT_REGISTER_INCOMPLETE")
    else:
        reason_codes.add("INPUT_REGISTER_REQUIRES_INDEPENDENT_VERIFICATION")

    return {
        "status": "DIAGNOSTIC_ONLY_NOT_READY",
        "pilot_ready": False,
        "launch_authorized": False,
        "release_eligible": False,
        "legal_clearance": False,
        "package_manifest_status": "VALID_NON_RELEASE_CANDIDATE" if manifest_valid else "INVALID",
        "input_register_status": register_result["status"],
        "input_register_missing_fields": register_result["missing_fields"],
        "startup_blocker_codes": startup_codes if manifest_valid else [],
        "reason_codes": sorted(reason_codes),
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--register", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = _read_json(args.manifest)
        register = _read_json(args.register)
    except (OSError, UnicodeError, json.JSONDecodeError):
        report = build_report(None, None)
        report["reason_codes"] = sorted(set(report["reason_codes"]) | {"INPUT_FILE_UNREADABLE_OR_INVALID_JSON"})
    else:
        report = build_report(manifest, register)
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
