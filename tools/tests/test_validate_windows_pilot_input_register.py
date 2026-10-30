from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate_windows_pilot_input_register import validate_register  # noqa: E402


def template() -> dict:
    return {
        "schema_version": 1,
        "references": {
            "product_public_key_sha256": None,
            "license_evidence_ref": None,
            "database_credential_target": "PLMProjectTool/Database",
            "service_identity_ref": None,
            "tls_certificate_thumbprint": None,
            "tls_dns_name": None,
        },
        "evidence_refs": {
            "license": None,
            "service_acl": None,
            "tls_chain_renewal": None,
            "database_scope": None,
        },
    }


class WindowsPilotInputRegisterTests(unittest.TestCase):
    def test_empty_template_is_incomplete_without_claiming_readiness(self) -> None:
        result = validate_register(template())
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertIn("product_public_key_sha256", result["missing_fields"])
        self.assertNotIn("READY", result["status"])

    def test_complete_metadata_still_requires_independent_verification(self) -> None:
        record = template()
        record["references"].update({
            "product_public_key_sha256": "a" * 64,
            "license_evidence_ref": "LIC-ISSUER-01",
            "service_identity_ref": r"NT SERVICE\PLMProjectTool",
            "tls_certificate_thumbprint": "b" * 40,
            "tls_dns_name": "pilot.example.com",
        })
        record["evidence_refs"].update({
            "license": "EVD-LIC-01",
            "service_acl": "EVD-ACL-01",
            "tls_chain_renewal": "EVD-TLS-01",
            "database_scope": "EVD-DB-01",
        })
        result = validate_register(record)
        self.assertEqual(result["status"], "COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION")

    def test_secret_like_extra_field_is_rejected_without_echo(self) -> None:
        record = template()
        record["private_key_pem"] = "SYNTHETIC_PRIVATE_KEY_MUST_NOT_ECHO"
        result = validate_register(record)
        rendered = json.dumps(result)
        self.assertEqual(result["status"], "INVALID")
        self.assertNotIn("SYNTHETIC_PRIVATE_KEY_MUST_NOT_ECHO", rendered)
        self.assertNotIn("private_key_pem", rendered)

    def test_malformed_reference_is_rejected_without_echo(self) -> None:
        record = template()
        record["references"]["product_public_key_sha256"] = "DO_NOT_ECHO_SECRET"
        result = validate_register(record)
        self.assertEqual(result["status"], "INVALID")
        self.assertNotIn("DO_NOT_ECHO_SECRET", json.dumps(result))

    def test_non_integer_schema_version_is_rejected(self) -> None:
        record = template()
        record["schema_version"] = 1.0
        self.assertEqual(validate_register(record)["status"], "INVALID")

    def test_cli_only_reports_status_and_safe_field_names(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-a37-register-") as temp:
            input_path = Path(temp) / "register.json"
            input_path.write_text(json.dumps(template()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] /
                                     "validate_windows_pilot_input_register.py"),
                 "--input", str(input_path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stderr, "")
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertNotIn(str(input_path), completed.stdout)


if __name__ == "__main__":
    unittest.main()
