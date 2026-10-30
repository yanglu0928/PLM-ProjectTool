from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_pilot_readiness_report import build_report  # noqa: E402


def register(*, complete: bool = False) -> dict:
    refs = {
        "product_public_key_sha256": None,
        "license_evidence_ref": None,
        "database_credential_target": "PLMProjectTool/Database",
        "service_identity_ref": None,
        "tls_certificate_thumbprint": None,
        "tls_dns_name": None,
    }
    evidence = {"license": None, "service_acl": None,
                "tls_chain_renewal": None, "database_scope": None}
    if complete:
        refs.update({"product_public_key_sha256": "a" * 64,
                     "license_evidence_ref": "LIC-01",
                     "service_identity_ref": r"NT SERVICE\PLMProjectTool",
                     "tls_certificate_thumbprint": "b" * 40,
                     "tls_dns_name": "pilot.example.com"})
        evidence.update({"license": "EVD-LIC-01", "service_acl": "EVD-ACL-01",
                         "tls_chain_renewal": "EVD-TLS-01", "database_scope": "EVD-DB-01"})
    return {"schema_version": 1, "references": refs, "evidence_refs": evidence}


def manifest(*, verified: bool = False) -> dict:
    startup = {
        "packaged_product_public_key_resource_present": verified,
        "formal_license_trust_verified": verified,
        "database_credential_reference_verified": verified,
        "database_credential_target_reference": "PLMProjectTool/Database",
        "service_identity_acl_verified": verified,
        "tls_certificate_configured": verified,
        "tls_private_key_configured": verified,
        "formal_startup_ready": verified,
        "blocker_codes": [] if verified else [
            "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
            "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
            "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
            "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
            "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
        ],
    }
    return {"kind": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE",
            "release_eligible": False, "legal_clearance": False,
            "startup_preflight": startup}


class WindowsPilotReadinessReportTests(unittest.TestCase):
    def test_incomplete_register_and_blocked_manifest_are_diagnosed(self) -> None:
        result = build_report(manifest(), register())
        self.assertEqual(result["status"], "DIAGNOSTIC_ONLY_NOT_READY")
        self.assertEqual(result["input_register_status"], "INCOMPLETE")
        self.assertIn("TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED", result["startup_blocker_codes"])
        self.assertFalse(result["launch_authorized"])
        self.assertFalse(result["pilot_ready"])

    def test_fully_claimed_candidate_and_complete_register_never_authorize(self) -> None:
        result = build_report(manifest(verified=True), register(complete=True))
        self.assertEqual(result["package_manifest_status"], "VALID_NON_RELEASE_CANDIDATE")
        self.assertEqual(result["input_register_status"], "COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION")
        self.assertIn("INPUT_REGISTER_REQUIRES_INDEPENDENT_VERIFICATION", result["reason_codes"])
        self.assertIn("NON_RELEASE_CANDIDATE", result["reason_codes"])
        self.assertFalse(result["release_eligible"])
        self.assertFalse(result["legal_clearance"])
        self.assertFalse(result["launch_authorized"])

    def test_malformed_manifest_is_invalid_and_unknown_values_are_not_echoed(self) -> None:
        candidate = manifest()
        candidate["startup_preflight"]["unexpected"] = "SYNTHETIC_SECRET_SENTINEL"
        result = build_report(candidate, register())
        self.assertEqual(result["package_manifest_status"], "INVALID")
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(result))
        self.assertNotIn("unexpected", json.dumps(result))

    def test_duplicate_declared_blocker_is_invalid(self) -> None:
        candidate = manifest()
        candidate["startup_preflight"]["blocker_codes"].append(
            candidate["startup_preflight"]["blocker_codes"][0])
        self.assertEqual(build_report(candidate, register())["package_manifest_status"], "INVALID")

    def test_invalid_register_value_is_not_echoed(self) -> None:
        candidate = register()
        candidate["private_key_pem"] = "SYNTHETIC_PRIVATE_SENTINEL"
        result = build_report(manifest(), candidate)
        self.assertEqual(result["input_register_status"], "INVALID")
        self.assertNotIn("SYNTHETIC_PRIVATE_SENTINEL", json.dumps(result))

    def test_cli_emits_non_authorizing_report_without_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-a38-report-") as temp:
            root = Path(temp)
            manifest_path = root / "manifest.json"
            register_path = root / "register.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            register_path.write_text(json.dumps(register()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] /
                                     "windows_pilot_readiness_report.py"),
                 "--manifest", str(manifest_path), "--register", str(register_path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        result = json.loads(completed.stdout)
        self.assertFalse(result["launch_authorized"])
        self.assertNotIn(str(root), completed.stdout)


if __name__ == "__main__":
    unittest.main()
