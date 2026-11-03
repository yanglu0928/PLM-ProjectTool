from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    PluginSignatureVerificationError,
    _signature_message,
)
from plm_assistant.modules.plugin.infrastructure import packaged_signer_resolver as resolver


def _manifest(records: list[dict[str, object]]) -> bytes:
    return json.dumps({
        "schema_version": "plm.plugin.publisher-keys.v1",
        "keys": records,
    }, separators=(",", ":")).encode("utf-8")


def _record(key_ref: str, public_key: bytes, state: str = "ACTIVE") -> dict[str, object]:
    return {
        "key_ref": key_ref,
        "algorithm": "Ed25519",
        "public_key": base64.b64encode(public_key).decode("ascii"),
        "state": state,
    }


class PackagedPluginSignerResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.key_ref = "synthetic:publisher-v1"

    def resolver_for(self, manifest_bytes: bytes) -> resolver.PackagedPluginSignerResolver:
        with patch.object(resolver, "_load_packaged_manifest", return_value=manifest_bytes):
            return resolver.PackagedPluginSignerResolver()

    def test_real_packaged_manifest_is_empty_and_fails_closed(self) -> None:
        packaged = resolver.PackagedPluginSignerResolver()
        self.assertIsNone(packaged.resolve_trusted_signer("any:publisher"))
        self.assertEqual(packaged._active_signers, {})

    def test_active_key_resolves_and_verifies_synthetic_signature(self) -> None:
        signer_resolver = self.resolver_for(_manifest([_record(self.key_ref, self.public)]))
        signer = signer_resolver.resolve_trusted_signer(self.key_ref)
        self.assertIsNotNone(signer)
        self.assertEqual(signer.signer_key_ref, self.key_ref)
        self.assertEqual(signer.public_key_raw, self.public)

        package_bytes = b"synthetic plugin archive only"
        digest = hashlib.sha256(package_bytes).digest()
        signature = self.private.sign(_signature_message(self.key_ref, digest))
        verifier = PluginPackageSignatureVerifier(signer_resolver)
        result = verifier.verify(
            package_bytes,
            signature=signature,
            signer_key_ref=self.key_ref,
        )
        self.assertEqual(result.package_sha256, digest)

    def test_unknown_revoked_and_malformed_key_refs_are_untrusted(self) -> None:
        active = self.resolver_for(_manifest([_record(self.key_ref, self.public)]))
        revoked_ref = "synthetic:revoked-v1"
        revoked = self.resolver_for(
            _manifest([_record(revoked_ref, self.public, "REVOKED")])
        )
        for source, ref in (
            (active, "unknown:publisher"),
            (revoked, revoked_ref),
            (active, "  " + self.key_ref),
            (active, "bad\x00ref"),
        ):
            self.assertIsNone(source.resolve_trusted_signer(ref))

    def test_invalid_manifest_shapes_fail_closed(self) -> None:
        valid = _record(self.key_ref, self.public)
        cases = [
            b"",
            b"not json",
            b'{"schema_version":"wrong","keys":[]}',
            b'{"schema_version":"plm.plugin.publisher-keys.v1","keys":[],"extra":true}',
            b'{"schema_version":"plm.plugin.publisher-keys.v1","keys":[],"keys":[]}',
            _manifest([valid, valid]),
            _manifest([{**valid, "algorithm": "RSA"}]),
            _manifest([{**valid, "state": "UNKNOWN"}]),
            _manifest([{**valid, "public_key": "%%%" }]),
            _manifest([{**valid, "public_key": base64.b64encode(b"short").decode()}]),
            _manifest([{**valid, "unknown": "field"}]),
        ]
        for candidate in cases:
            with self.subTest(size=len(candidate)):
                with self.assertRaises(resolver.PluginTrustConfigurationError):
                    self.resolver_for(candidate)

    def test_oversized_or_excessive_keyrings_fail_closed(self) -> None:
        with self.assertRaises(resolver.PluginTrustConfigurationError):
            self.resolver_for(b" " * (resolver._MAX_MANIFEST_BYTES + 1))
        too_many = [_record(f"publisher:{i}", self.public) for i in range(129)]
        with self.assertRaises(resolver.PluginTrustConfigurationError):
            self.resolver_for(_manifest(too_many))

    def test_verifier_maps_missing_or_corrupt_trust_to_untrusted(self) -> None:
        broken = resolver.PackagedPluginSignerResolver.__new__(
            resolver.PackagedPluginSignerResolver
        )
        broken._active_signers = {}
        verifier = PluginPackageSignatureVerifier(broken)
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            verifier.verify(
                b"synthetic archive",
                signature=b"x" * 64,
                signer_key_ref=self.key_ref,
            )
        self.assertEqual(caught.exception.code, "PLUGIN_SIGNER_UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
