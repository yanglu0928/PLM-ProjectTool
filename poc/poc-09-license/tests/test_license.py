from __future__ import annotations

import copy
import importlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

POC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_ROOT / "src"))

from poc09_license import (  # noqa: E402
    LicenseError,
    LicensePayload,
    MacCandidate,
    SystemTimeGuard,
    create_license_request,
    issue_license,
    machine_fingerprint,
    normalize_mac,
    public_key_to_base64,
    select_mac,
    verify_license,
)

mac_module = importlib.import_module("poc09_license.mac")


UTC = timezone.utc
BASE_TIME = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)
MAC = "02:11:22:33:44:55"


class LicenseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = public_key_to_base64(self.private_key.public_key())
        self.payload = LicensePayload.create(
            license_id="LIC-POC-0001",
            customer="POC Customer",
            machine_fingerprint=machine_fingerprint(MAC),
            issue_time=BASE_TIME,
            valid_from=BASE_TIME,
            valid_to=BASE_TIME + timedelta(days=30),
        )
        self.document = issue_license(self.payload, self.private_key).as_dict()

    def assert_license_error(self, code: str, function, *args, **kwargs) -> None:
        with self.assertRaises(LicenseError) as context:
            function(*args, **kwargs)
        self.assertEqual(code, context.exception.code)

    def test_normalize_mac_variants(self) -> None:
        variants = ["02-11-22-33-44-55", "0211.2233.4455", " 02:11:22:33:44:55 "]
        self.assertEqual({"02:11:22:33:44:55"}, {normalize_mac(item) for item in variants})

    def test_invalid_mac_rejected(self) -> None:
        for value in ("", "not-a-mac", "00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"):
            self.assert_license_error("LICENSE_MAC_INVALID", normalize_mac, value)

    def test_fingerprint_is_stable_sha256(self) -> None:
        self.assertEqual(machine_fingerprint(MAC), machine_fingerprint("0211.2233.4455"))
        self.assertEqual(64, len(machine_fingerprint(MAC)))

    def test_operator_selection_is_required(self) -> None:
        candidates = [MacCandidate("adapter", MAC, "Up")]
        self.assert_license_error("LICENSE_MAC_SELECTION_REQUIRED", select_mac, candidates, None)

    def test_unavailable_selection_rejected(self) -> None:
        candidates = [MacCandidate("adapter", MAC, "Up")]
        self.assert_license_error("LICENSE_MAC_NOT_AVAILABLE", select_mac, candidates, "02:AA:BB:CC:DD:EE")

    def test_license_request_contains_fingerprint_not_raw_mac(self) -> None:
        request = create_license_request([MacCandidate("adapter", MAC, "Up")], MAC)
        self.assertEqual("plm.license-request.v1", request["schema_version"])
        self.assertNotIn(MAC, str(request))

    def test_valid_license_passes(self) -> None:
        result = verify_license(self.document, public_key_base64=self.public_key, current_mac=MAC, now=BASE_TIME)
        self.assertEqual("LIC-POC-0001", result.license_id)

    def test_mac_change_rejected(self) -> None:
        self.assert_license_error(
            "LICENSE_MACHINE_MISMATCH",
            verify_license,
            self.document,
            public_key_base64=self.public_key,
            current_mac="02:11:22:33:44:56",
            now=BASE_TIME,
        )

    def test_expired_license_rejected(self) -> None:
        self.assert_license_error(
            "LICENSE_EXPIRED",
            verify_license,
            self.document,
            public_key_base64=self.public_key,
            current_mac=MAC,
            now=BASE_TIME + timedelta(days=31),
        )

    def test_not_yet_valid_license_rejected(self) -> None:
        payload = LicensePayload.create(
            license_id="LIC-FUTURE",
            customer="POC Customer",
            machine_fingerprint=machine_fingerprint(MAC),
            issue_time=BASE_TIME,
            valid_from=BASE_TIME + timedelta(days=1),
            valid_to=BASE_TIME + timedelta(days=31),
        )
        document = issue_license(payload, self.private_key).as_dict()
        self.assert_license_error(
            "LICENSE_NOT_YET_VALID", verify_license, document,
            public_key_base64=self.public_key, current_mac=MAC, now=BASE_TIME + timedelta(hours=1)
        )

    def test_system_time_before_issue_rejected(self) -> None:
        self.assert_license_error(
            "LICENSE_SYSTEM_TIME_INVALID",
            verify_license,
            self.document,
            public_key_base64=self.public_key,
            current_mac=MAC,
            now=BASE_TIME - timedelta(seconds=1),
        )

    def test_clock_rollback_rejected(self) -> None:
        guard = SystemTimeGuard()
        verify_license(
            self.document, public_key_base64=self.public_key, current_mac=MAC,
            now=BASE_TIME + timedelta(days=2), time_guard=guard
        )
        self.assert_license_error(
            "LICENSE_CLOCK_ROLLBACK", verify_license, self.document,
            public_key_base64=self.public_key, current_mac=MAC,
            now=BASE_TIME + timedelta(days=1), time_guard=guard
        )

    def test_payload_tamper_rejected(self) -> None:
        tampered = copy.deepcopy(self.document)
        tampered["payload"]["customer"] = "Tampered"
        self.assert_license_error(
            "LICENSE_SIGNATURE_INVALID", verify_license, tampered,
            public_key_base64=self.public_key, current_mac=MAC, now=BASE_TIME
        )

    def test_signature_tamper_rejected(self) -> None:
        tampered = copy.deepcopy(self.document)
        replacement = "A" if tampered["signature"][-1] != "A" else "B"
        tampered["signature"] = tampered["signature"][:-1] + replacement
        self.assert_license_error(
            "LICENSE_SIGNATURE_INVALID", verify_license, tampered,
            public_key_base64=self.public_key, current_mac=MAC, now=BASE_TIME
        )

    def test_wrong_public_key_rejected(self) -> None:
        wrong = public_key_to_base64(Ed25519PrivateKey.generate().public_key())
        self.assert_license_error(
            "LICENSE_SIGNATURE_INVALID", verify_license, self.document,
            public_key_base64=wrong, current_mac=MAC, now=BASE_TIME
        )

    def test_malformed_public_key_rejected(self) -> None:
        self.assert_license_error(
            "LICENSE_PUBLIC_KEY_INVALID", verify_license, self.document,
            public_key_base64="not-base64", current_mac=MAC, now=BASE_TIME
        )

    def test_unexpected_document_field_rejected(self) -> None:
        malformed = copy.deepcopy(self.document)
        malformed["private_key"] = "must-never-be-accepted"
        self.assert_license_error(
            "LICENSE_DOCUMENT_INVALID", verify_license, malformed,
            public_key_base64=self.public_key, current_mac=MAC, now=BASE_TIME
        )

    def test_invalid_payload_time_range_rejected_before_signing(self) -> None:
        self.assert_license_error(
            "LICENSE_PAYLOAD_INVALID",
            LicensePayload.create,
            license_id="LIC-BAD-RANGE",
            customer="POC Customer",
            machine_fingerprint=machine_fingerprint(MAC),
            issue_time=BASE_TIME,
            valid_from=BASE_TIME + timedelta(days=2),
            valid_to=BASE_TIME + timedelta(days=1),
        )

    def test_license_error_serialization(self) -> None:
        error = LicenseError("LICENSE_TEST", "test")
        self.assertEqual({"code": "LICENSE_TEST", "message": "test"}, error.as_dict())

    def test_windows_discovery_parses_and_filters_rows(self) -> None:
        output = '[{"InterfaceDescription":"NIC 1","MacAddress":"02-11-22-33-44-55","Status":"Up"},{"MacAddress":"bad"}]'
        completed = SimpleNamespace(returncode=0, stdout=output, stderr="")
        with patch.object(mac_module.subprocess, "run", return_value=completed):
            result = mac_module._discover_windows()
        self.assertEqual([MacCandidate("NIC 1", MAC, "Up")], result)

    def test_windows_discovery_command_failure_is_controlled(self) -> None:
        completed = SimpleNamespace(returncode=1, stdout="", stderr="failed")
        with patch.object(mac_module.subprocess, "run", return_value=completed):
            self.assert_license_error("LICENSE_MAC_DISCOVERY_FAILED", mac_module._discover_windows)

    def test_windows_discovery_invalid_json_is_controlled(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="not-json", stderr="")
        with patch.object(mac_module.subprocess, "run", return_value=completed):
            self.assert_license_error("LICENSE_MAC_DISCOVERY_FAILED", mac_module._discover_windows)

    def test_linux_discovery_reads_sysfs_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter = Path(temporary) / "eth0"
            adapter.mkdir()
            address = adapter / "address"
            address.write_text("02:11:22:33:44:55\n", encoding="ascii")
            (adapter / "operstate").write_text("up\n", encoding="ascii")
            with patch.object(mac_module.Path, "glob", return_value=[address]):
                result = mac_module._discover_linux()
        self.assertEqual([MacCandidate("eth0", MAC, "up")], result)

    def test_discovery_rejects_unsupported_operating_system(self) -> None:
        with patch.object(mac_module.platform, "system", return_value="Darwin"):
            self.assert_license_error("LICENSE_OS_UNSUPPORTED", mac_module.discover_mac_candidates)

    def test_discovery_rejects_empty_candidate_list(self) -> None:
        with patch.object(mac_module.platform, "system", return_value="Windows"), patch.object(
            mac_module, "_discover_windows", return_value=[]
        ):
            self.assert_license_error("LICENSE_MAC_NOT_FOUND", mac_module.discover_mac_candidates)

    def test_discovery_deduplicates_and_prefers_up_adapters(self) -> None:
        candidates = [
            MacCandidate("z-down", "02:AA:BB:CC:DD:EE", "Disconnected"),
            MacCandidate("b-up", MAC, "Up"),
            MacCandidate("a-duplicate", MAC, "Up"),
        ]
        with patch.object(mac_module.platform, "system", return_value="Windows"), patch.object(
            mac_module, "_discover_windows", return_value=candidates
        ):
            result = mac_module.discover_mac_candidates()
        self.assertEqual(["a-duplicate", "z-down"], [item.interface for item in result])


if __name__ == "__main__":
    unittest.main()
