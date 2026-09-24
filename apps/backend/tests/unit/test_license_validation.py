from __future__ import annotations

import base64
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.license.application.license_validation import (
    LicenseService, LicenseValidationError, PRODUCT_CODE, machine_fingerprint_hash, normalize_mac,
)
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.application.trusted_time import TrustedTimeError
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver


def document(private_key, payload):
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return json.dumps({"algorithm": "Ed25519", "payload": payload,
                       "signature": base64.b64encode(private_key.sign(canonical)).decode("ascii")},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Machine:
    def __init__(self, mac="00:11:22:33:44:55"):
        self.mac = mac

    def selected_mac(self):
        return self.mac


class ProductKey:
    def __init__(self, ref="plm-project-tool-release-v1"):
        self.ref = ref

    def product_key_ref(self):
        return self.ref


class Clock:
    def __init__(self, now):
        self.now = now

    def now_utc(self):
        return self.now


class TrustedTime:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def advance(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error


class LicenseValidationTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()  # ephemeral, test process only
        public = self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.signature = LicenseSignatureVerifier(StaticPublicKeyResolver({"plm-project-tool-release-v1": public}))
        self.machine = Machine()
        self.product_key = ProductKey()
        self.now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
        self.clock = Clock(self.now)
        self.time = TrustedTime()
        self.trace = uuid.uuid4()
        self.payload = {
            "license_id": "synthetic-license-001", "customer": "合成客户",
            "machine_fingerprint": machine_fingerprint_hash(self.machine.mac).hex(),
            "valid_from": "2026-09-01T00:00:00Z", "valid_to": "2026-10-01T00:00:00Z",
            "issue_time": "2026-08-31T00:00:00Z", "schema_version": "plm.license.v1",
        }

    def service(self):
        return LicenseService(self.signature, self.machine, self.product_key, self.clock, self.time)

    def validate(self, payload=None):
        return self.service().validate(document(self.private, payload or self.payload),
                                       expected_time_version=1, trace_id=self.trace)

    def reject(self, code, payload=None):
        with self.assertRaises(LicenseValidationError) as caught:
            self.validate(payload)
        self.assertEqual(caught.exception.code, code)

    def test_full_bundle_is_derived_from_dedicated_key_not_payload_claim(self):
        result = self.validate()
        self.assertEqual(result.product_code, PRODUCT_CODE)
        self.assertEqual(result.grant_scope, "FULL_BUNDLE")
        self.assertEqual(result.machine_fingerprint_hash, machine_fingerprint_hash(self.machine.mac))
        self.assertEqual(result.validated_at, self.now)
        self.assertNotIn("合成客户", repr(result))
        self.assertEqual(len(self.time.calls), 1)
        self.assertEqual(self.time.calls[0]["expected_version"], 1)
        self.assertEqual(self.time.calls[0]["rollback_tolerance"], timedelta(0))

    def test_seven_field_v1_schema_and_ranges(self):
        for changed in (
            {**self.payload, "features": ["all"]},
            {k: v for k, v in self.payload.items() if k != "customer"},
            {**self.payload, "schema_version": "plm.license.v2"},
            {**self.payload, "machine_fingerprint": "bad"},
            {**self.payload, "customer": " "},
            {**self.payload, "valid_from": "2026-11-01T00:00:00Z"},
            {**self.payload, "valid_to": "not-a-time"},
            {**self.payload, "valid_from": "2026-09-01"},
        ):
            self.reject("MALFORMED", changed)
        self.assertEqual(self.time.calls, [])

    def test_machine_mismatch_expiry_not_yet_valid_and_clock_policy(self):
        self.machine.mac = "00:11:22:33:44:56"
        self.reject("MACHINE_MISMATCH")
        self.machine.mac = "00:11:22:33:44:55"
        self.clock.now = datetime(2026, 8, 30, tzinfo=timezone.utc)
        self.reject("NOT_YET_VALID")
        self.clock.now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        self.reject("EXPIRED")
        self.clock.now = self.now
        self.time.error = TrustedTimeError("TIME_ROLLBACK")
        self.reject("TIME_ROLLBACK")
        self.time.error = TrustedTimeError("TRUST_STATE_INVALID")
        self.reject("TRUST_STATE_INVALID")

    def test_tampered_signature_unknown_product_key_and_wrong_key(self):
        raw = json.loads(document(self.private, self.payload))
        raw["payload"]["customer"] = "tampered"
        with self.assertRaises(LicenseValidationError) as caught:
            self.service().validate(json.dumps(raw).encode(), expected_time_version=1, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "SIGNATURE_INVALID")
        self.product_key.ref = "unknown-product-key"
        self.reject("TRUST_STATE_INVALID")
        self.product_key.ref = "plm-project-tool-release-v1"
        other = Ed25519PrivateKey.generate()
        with self.assertRaises(LicenseValidationError) as caught:
            self.service().validate(document(other, self.payload), expected_time_version=1, trace_id=self.trace)
        self.assertEqual(caught.exception.code, "SIGNATURE_INVALID")

    def test_missing_trusted_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            LicenseService(None, self.machine, self.product_key, self.clock, self.time)
        for bad in ("garbage", "00:00:00:00:00:00"):
            with self.assertRaises(LicenseValidationError):
                normalize_mac(bad)
        self.assertEqual(normalize_mac("00-11-22-33-44-55"), "00:11:22:33:44:55")
        self.product_key.ref = ""
        self.reject("TRUST_STATE_INVALID")
        self.product_key.ref = "plm-project-tool-release-v1"
        self.machine.mac = "bad"
        self.reject("TRUST_STATE_INVALID")
        self.machine.mac = "00:11:22:33:44:55"
        self.clock.now = datetime(2026, 9, 24)  # naive time is not accepted
        self.reject("TRUST_STATE_INVALID")
        self.clock.now = self.now
        with self.assertRaises(LicenseValidationError):
            self.service().validate(document(self.private, self.payload), expected_time_version=True,
                                    trace_id=self.trace)


if __name__ == "__main__":
    unittest.main()
