from __future__ import annotations

import base64
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.license.application.signature_verifier import (
    LicenseSignatureError, LicenseSignatureVerifier,
)
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver


def signed_document(private_key, payload=None):
    payload = payload if payload is not None else {"schema_version": "plm.license.v1", "customer": "合成客户"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = base64.b64encode(private_key.sign(canonical)).decode("ascii")
    return json.dumps({"algorithm": "Ed25519", "payload": payload, "signature": signature},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class LicenseSignatureVerifierTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()  # test-only, in-memory; never serialized
        public = self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.verifier = LicenseSignatureVerifier(StaticPublicKeyResolver({"release-v1": public}))
        self.document = signed_document(self.private)

    def reject(self, document, code="LICENSE_DOCUMENT_INVALID", ref="release-v1"):
        with self.assertRaises(LicenseSignatureError) as caught:
            self.verifier.verify(document, public_key_ref=ref)
        self.assertEqual(caught.exception.code, code)

    def test_valid_signature_is_only_authenticity_not_license_validity(self):
        result = self.verifier.verify(self.document, public_key_ref="release-v1")
        self.assertEqual(result.public_key_ref, "release-v1")
        self.assertEqual(len(result.document_sha256), 32)
        self.assertIn("合成客户".encode("utf-8"), result.canonical_payload)
        self.assertNotIn("合成客户", repr(result))

    def test_payload_tamper_and_wrong_key_rejected(self):
        raw = json.loads(self.document)
        raw["payload"]["customer"] = "tampered"
        self.reject(json.dumps(raw, ensure_ascii=False).encode("utf-8"), "LICENSE_SIGNATURE_INVALID")
        self.reject(self.document, "LICENSE_PUBLIC_KEY_INVALID", ref="unknown")
        other = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        verifier = LicenseSignatureVerifier(StaticPublicKeyResolver({"release-v1": other}))
        with self.assertRaises(LicenseSignatureError):
            verifier.verify(self.document, public_key_ref="release-v1")

    def test_envelope_and_duplicate_keys_rejected(self):
        self.reject(b'{"algorithm":"Ed25519","algorithm":"Ed25519","payload":{},"signature":"AA=="}')
        self.reject(b'{"algorithm":"Ed25519","payload":{"x":1,"x":2},"signature":"AA=="}')
        self.reject(b'{"algorithm":"RSA","payload":{},"signature":"AA=="}')
        self.reject(b'{"algorithm":"Ed25519","payload":[],"signature":"AA=="}')
        self.reject(b'{"algorithm":"Ed25519","payload":{"x":NaN},"signature":"AA=="}')
        self.reject(b"\xff")
        self.reject(b"")
        self.reject(b"x" * 65_537)

    def test_bad_signature_encoding_and_payload_shape_rejected(self):
        raw = json.loads(self.document)
        raw["signature"] = "not base64!"
        self.reject(json.dumps(raw).encode(), "LICENSE_SIGNATURE_INVALID")
        raw["signature"] = base64.b64encode(b"short").decode()
        self.reject(json.dumps(raw).encode(), "LICENSE_SIGNATURE_INVALID")
        raw["payload"]["float"] = 1.5
        self.reject(json.dumps(raw).encode())
        raw["payload"].pop("float")
        raw["payload"]["null"] = None
        self.reject(json.dumps(raw).encode())

    def test_depth_and_node_limits(self):
        deep = {"leaf": "x"}
        for _ in range(17):
            deep = {"nested": deep}
        self.reject(signed_document(self.private, deep))
        self.reject(signed_document(self.private, {str(n): n for n in range(1025)}))

    def test_resolver_requires_configured_public_keys(self):
        with self.assertRaises(ValueError):
            StaticPublicKeyResolver({})
        with self.assertRaises(ValueError):
            StaticPublicKeyResolver({"bad": b"short"})
        with self.assertRaises(ValueError):
            LicenseSignatureVerifier(None)


if __name__ == "__main__":
    unittest.main()
