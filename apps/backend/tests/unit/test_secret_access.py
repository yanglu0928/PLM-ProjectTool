from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError,
    SecretConsumer,
    SecretEnvelope,
    SecretPurpose,
    SecretRef,
    SecretResolver,
    SecretState,
)
from plm_assistant.modules.platform.application.trace_context import trace_scope


TRACE_ID = "018f0000-0000-7000-8000-000000000001"
SECRET_REF = SecretRef(uuid.UUID("018f0000-0000-7000-8000-000000000002"))


class FakeStore:
    def __init__(self, envelope: SecretEnvelope | None) -> None:
        self.envelope = envelope

    def load(self, secret_ref: SecretRef) -> SecretEnvelope | None:
        return self.envelope


class FakeDecryptor:
    def __init__(self) -> None:
        self.buffer = bytearray(b"synthetic-only")
        self.calls = 0

    def decrypt(self, envelope: SecretEnvelope) -> bytearray:
        self.calls += 1
        return self.buffer


class FailingDecryptor:
    def decrypt(self, envelope: SecretEnvelope) -> bytearray:
        raise RuntimeError("ciphertext and path must not leak")


class FakeAudit:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[dict[str, object]] = []
        self.fail = fail

    def record_access(self, **event: object) -> None:
        if self.fail:
            raise RuntimeError("audit unavailable with secret")
        self.events.append(event)


def envelope() -> SecretEnvelope:
    return SecretEnvelope(
        secret_ref=SECRET_REF,
        purpose=SecretPurpose.AI_PROVIDER_KEY,
        state=SecretState.ACTIVE,
        allowed_consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
        version_no=1,
        encrypted_payload=b"opaque-ciphertext",
        encryption_metadata=b"opaque-metadata",
        key_provider_ref="external-provider",
    )


class SecretAccessTests(unittest.TestCase):
    def test_authorized_single_call_zeroizes_buffer_and_audits(self) -> None:
        decryptor = FakeDecryptor()
        audit = FakeAudit()
        resolver = SecretResolver(FakeStore(envelope()), decryptor, audit)
        with trace_scope(TRACE_ID):
            with resolver.use(SECRET_REF, SecretConsumer.AI_PROVIDER_ADAPTER) as value:
                self.assertEqual(value.tobytes(), b"synthetic-only")
        self.assertEqual(decryptor.buffer, bytearray(len(decryptor.buffer)))
        self.assertEqual(decryptor.calls, 1)
        self.assertEqual(len(audit.events), 1)
        self.assertEqual(audit.events[0]["outcome"], "GRANTED")
        self.assertEqual(audit.events[0]["trace_id"], TRACE_ID)

    def test_denies_wrong_consumer_before_decryption(self) -> None:
        decryptor = FakeDecryptor()
        audit = FakeAudit()
        resolver = SecretResolver(FakeStore(envelope()), decryptor, audit)
        with self.assertRaises(SecretAccessError):
            with resolver.use(SECRET_REF, SecretConsumer.DATABASE_ADAPTER):
                pass
        self.assertEqual(decryptor.calls, 0)
        self.assertEqual(audit.events[0]["outcome"], "DENIED")

    def test_disabled_or_mismatched_record_fails_closed(self) -> None:
        for record in (
            replace(envelope(), state=SecretState.DISABLED),
            replace(envelope(), purpose=SecretPurpose.DATABASE_PASSWORD),
            replace(envelope(), secret_ref=SecretRef(uuid.uuid4())),
            replace(envelope(), encrypted_payload=b""),
            replace(envelope(), key_provider_ref=""),
            None,
        ):
            with self.subTest(record=record):
                decryptor = FakeDecryptor()
                audit = FakeAudit()
                resolver = SecretResolver(FakeStore(record), decryptor, audit)
                with self.assertRaises(SecretAccessError):
                    with resolver.use(SECRET_REF, SecretConsumer.AI_PROVIDER_ADAPTER):
                        pass
                self.assertEqual(decryptor.calls, 0)
                self.assertEqual(audit.events[0]["outcome"], "DENIED")

    def test_audit_failure_denies_and_zeroizes(self) -> None:
        decryptor = FakeDecryptor()
        resolver = SecretResolver(FakeStore(envelope()), decryptor, FakeAudit(fail=True))
        with self.assertRaises(SecretAccessError) as captured:
            with resolver.use(SECRET_REF, SecretConsumer.AI_PROVIDER_ADAPTER):
                pass
        self.assertEqual(str(captured.exception), "secret unavailable")
        self.assertEqual(decryptor.buffer, bytearray(len(decryptor.buffer)))
        self.assertNotIn("audit unavailable", str(captured.exception))

    def test_decrypt_failure_is_audited_and_redacted(self) -> None:
        audit = FakeAudit()
        resolver = SecretResolver(FakeStore(envelope()), FailingDecryptor(), audit)
        with self.assertRaises(SecretAccessError) as captured:
            with resolver.use(SECRET_REF, SecretConsumer.AI_PROVIDER_ADAPTER):
                pass
        self.assertEqual(audit.events[0]["outcome"], "DENIED")
        self.assertEqual(str(captured.exception), "secret unavailable")

    def test_sensitive_envelope_repr_is_redacted(self) -> None:
        text = repr(envelope())
        self.assertNotIn("opaque-ciphertext", text)
        self.assertNotIn("opaque-metadata", text)
        self.assertNotIn("external-provider", text)


if __name__ == "__main__":
    unittest.main()
