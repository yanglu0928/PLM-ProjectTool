from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    PluginSignatureVerificationError,
    TrustedPluginSigner,
    _signature_message,
)


class SyntheticSignerResolver:
    def __init__(self, signer: TrustedPluginSigner | None) -> None:
        self.signer = signer

    def resolve_trusted_signer(self, signer_key_ref: str) -> TrustedPluginSigner | None:
        if self.signer is not None and self.signer.signer_key_ref == signer_key_ref:
            return self.signer
        return None


class RaisingSignerResolver:
    def resolve_trusted_signer(self, signer_key_ref: str) -> TrustedPluginSigner | None:
        raise RuntimeError("synthetic trust source failure")


class PluginPackageSignatureVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()  # runtime-only synthetic key
        public_key = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.signer = TrustedPluginSigner("workbench:release-v1", public_key)
        self.package_bytes = b"synthetic complete plugin archive"
        digest = hashlib.sha256(self.package_bytes).digest()
        self.signature = self.private_key.sign(
            _signature_message(self.signer.signer_key_ref, digest)
        )
        self.verifier = PluginPackageSignatureVerifier(
            SyntheticSignerResolver(self.signer)
        )

    def reject(self, package: object, signature: object, ref: object, code: str) -> None:
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            self.verifier.verify(package, signature=signature, signer_key_ref=ref)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(self.package_bytes.decode(), str(caught.exception))
        self.assertNotIn(self.signer.public_key_raw.hex(), str(caught.exception))

    def test_valid_signature_binds_complete_package_and_trusted_key_ref(self) -> None:
        result = self.verifier.verify(
            self.package_bytes,
            signature=self.signature,
            signer_key_ref=self.signer.signer_key_ref,
        )
        self.assertEqual(result.signer_key_ref, self.signer.signer_key_ref)
        self.assertEqual(result.package_sha256, hashlib.sha256(self.package_bytes).digest())
        self.assertEqual(result.algorithm, "Ed25519")
        self.assertNotIn(self.signer.public_key_raw.hex(), repr(self.signer))

    def test_package_or_signature_tampering_is_rejected(self) -> None:
        self.reject(
            self.package_bytes + b"!",
            self.signature,
            self.signer.signer_key_ref,
            "PLUGIN_SIGNATURE_INVALID",
        )
        altered = bytes([self.signature[0] ^ 1]) + self.signature[1:]
        self.reject(
            self.package_bytes,
            altered,
            self.signer.signer_key_ref,
            "PLUGIN_SIGNATURE_INVALID",
        )

    def test_unknown_signer_is_rejected_without_request_supplied_key(self) -> None:
        self.reject(
            self.package_bytes,
            self.signature,
            "untrusted:attacker",
            "PLUGIN_SIGNER_UNTRUSTED",
        )

    def test_inactive_or_revoked_signer_is_rejected(self) -> None:
        for state in ("DISABLED", "REVOKED", "EXPIRED"):
            resolver = SyntheticSignerResolver(replace(self.signer, state=state))
            verifier = PluginPackageSignatureVerifier(resolver)
            with self.assertRaises(PluginSignatureVerificationError) as caught:
                verifier.verify(
                    self.package_bytes,
                    signature=self.signature,
                    signer_key_ref=self.signer.signer_key_ref,
                )
            self.assertEqual(caught.exception.code, "PLUGIN_SIGNER_UNTRUSTED")

    def test_malformed_trust_record_or_unavailable_resolver_fails_closed(self) -> None:
        malformed = replace(self.signer, public_key_raw=b"short")
        verifier = PluginPackageSignatureVerifier(SyntheticSignerResolver(malformed))
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            verifier.verify(
                self.package_bytes,
                signature=self.signature,
                signer_key_ref=self.signer.signer_key_ref,
            )
        self.assertEqual(caught.exception.code, "PLUGIN_SIGNER_UNTRUSTED")

        verifier = PluginPackageSignatureVerifier(RaisingSignerResolver())
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            verifier.verify(
                self.package_bytes,
                signature=self.signature,
                signer_key_ref=self.signer.signer_key_ref,
            )
        self.assertEqual(caught.exception.code, "PLUGIN_SIGNER_UNTRUSTED")

    def test_invalid_package_signature_and_key_ref_shapes_are_rejected(self) -> None:
        cases = [
            (b"", self.signature, self.signer.signer_key_ref, "PLUGIN_PACKAGE_INVALID"),
            (None, self.signature, self.signer.signer_key_ref, "PLUGIN_PACKAGE_INVALID"),
            (self.package_bytes, b"short", self.signer.signer_key_ref, "PLUGIN_SIGNATURE_INVALID"),
            (self.package_bytes, self.signature, "", "PLUGIN_PACKAGE_INVALID"),
            (self.package_bytes, self.signature, " ref ", "PLUGIN_PACKAGE_INVALID"),
            (self.package_bytes, self.signature, "a\x00b", "PLUGIN_PACKAGE_INVALID"),
            (self.package_bytes, self.signature, "x" * 513, "PLUGIN_PACKAGE_INVALID"),
        ]
        for package, signature, ref, code in cases:
            self.reject(package, signature, ref, code)

    def test_key_reference_length_prefix_and_domain_are_part_of_message(self) -> None:
        digest = hashlib.sha256(self.package_bytes).digest()
        message_a = _signature_message("ab", digest)
        message_b = _signature_message("a", hashlib.sha256(b"b" + self.package_bytes).digest())
        self.assertNotEqual(message_a, message_b)
        self.assertTrue(message_a.startswith(b"PLM-PLUGIN-PACKAGE\x00v1\x00"))

    def test_verifier_requires_trusted_resolver(self) -> None:
        with self.assertRaises(ValueError):
            PluginPackageSignatureVerifier(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
