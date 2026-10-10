from __future__ import annotations

import json
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretState,
)
from plm_assistant.modules.platform.infrastructure.secret_crypto import (
    ALGORITHM, AesGcmSecretCrypto, SecretCryptoError,
)


class Provider:
    def __init__(self):
        self.key = b"s" * 32

    def resolve_key(self, key_ref):
        return self.key if key_ref == "synthetic-key" else None


class SecretCryptoTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.crypto = AesGcmSecretCrypto(self.provider, key_ref="synthetic-key")
        self.ref = SecretRef(uuid.uuid4())

    def encrypt_envelope(self):
        clear = bytearray(b"synthetic-only")
        draft = self.crypto.encrypt(
            secret_ref=self.ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
            consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
            version_no=1, plaintext=clear,
        )
        self.assertEqual(clear, bytearray(len(clear)))
        return SecretEnvelope(
            self.ref, SecretPurpose.AI_PROVIDER_KEY, SecretState.ACTIVE,
            SecretConsumer.AI_PROVIDER_ADAPTER, 1,
            draft.encrypted_payload, draft.encryption_metadata,
            draft.key_provider_ref,
        )

    def test_round_trip_nonce_uniqueness_and_redaction(self):
        envelope = self.encrypt_envelope()
        first = self.crypto.decrypt(envelope)
        self.assertEqual(first, bytearray(b"synthetic-only"))
        first[:] = b"\x00" * len(first)
        second = self.encrypt_envelope()
        self.assertNotEqual(envelope.encryption_metadata, second.encryption_metadata)
        self.assertNotIn("synthetic-only", repr(second))
        self.assertEqual(json.loads(second.encryption_metadata)["algorithm"], ALGORITHM)

    def test_tampering_and_wrong_context_are_rejected(self):
        envelope = self.encrypt_envelope()
        mutated = bytearray(envelope.encrypted_payload)
        mutated[0] ^= 1
        bad_metadata = json.dumps({"algorithm": ALGORITHM, "nonce": "AAAA"}).encode()
        for candidate in (
            replace(envelope, encrypted_payload=bytes(mutated)),
            replace(envelope, encryption_metadata=bad_metadata),
            replace(envelope, encryption_metadata=b'{"algorithm":"LEGACY","nonce":"AAAAAAAAAAAAAAAA"}'),
            replace(envelope, secret_ref=SecretRef(uuid.uuid4())),
            replace(envelope, purpose=SecretPurpose.RERANKER_KEY),
            replace(envelope, allowed_consumer=SecretConsumer.RERANKER_ADAPTER),
            replace(envelope, version_no=2),
            replace(envelope, key_provider_ref="other-key"),
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(SecretCryptoError):
                    self.crypto.decrypt(candidate)

    def test_missing_key_fails_closed(self):
        self.provider.key = None
        clear = bytearray(b"synthetic-only")
        with self.assertRaises(SecretCryptoError):
            self.crypto.encrypt(
                secret_ref=self.ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
                consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
                version_no=1, plaintext=clear,
            )
        self.assertEqual(clear, bytearray(len(clear)))

    def test_size_and_type_bounds(self):
        for value in (bytearray(), bytearray(65521), b"immutable"):
            with self.subTest(size=len(value)):
                with self.assertRaises(SecretCryptoError):
                    self.crypto.encrypt(
                        secret_ref=self.ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
                        consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
                        version_no=1, plaintext=value,
                    )


if __name__ == "__main__":
    unittest.main()
