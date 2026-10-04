from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    RetrievalQueryCryptoError,
    RetrievalQueryEnvelope,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import (
    AesGcmRetrievalQueryCrypto,
)


class _Keys:
    def __init__(self):
        self.key = b"k" * 32

    def resolve_key(self, key_ref):
        return self.key if key_ref == "rag-query-key.v1" else None


class RAGRetrievalQueryCryptoTests(unittest.TestCase):
    def setUp(self):
        self.crypto = AesGcmRetrievalQueryCrypto(
            _Keys(), key_ref="rag-query-key.v1")
        self.run, self.project = uuid.uuid4(), uuid.uuid4()
        self.until = datetime.now(timezone.utc) + timedelta(days=180)

    def test_roundtrip_uses_bound_aad_and_zeros_input(self):
        plaintext = bytearray("中文 PLM 查询".encode("utf-8"))
        expected = bytes(plaintext)
        draft = self.crypto.encrypt(
            retrieval_run_id=self.run, project_id=self.project,
            query_fingerprint=b"q" * 32, plaintext=plaintext,
            retention_until=self.until)
        self.assertEqual(plaintext, bytearray(len(plaintext)))
        self.assertNotEqual(draft.encrypted_payload, expected)
        envelope = RetrievalQueryEnvelope(
            draft.retrieval_run_id, draft.project_id, draft.query_fingerprint,
            draft.encrypted_payload, draft.encryption_metadata,
            draft.key_provider_ref, draft.plaintext_bytes, draft.retention_until)
        result = self.crypto.decrypt(envelope)
        self.assertEqual(bytes(result), expected)
        result[:] = b"\x00" * len(result)
        self.assertNotIn("中文", repr(draft))
        self.assertNotIn(draft.encrypted_payload.hex(), repr(draft))

    def test_identity_fingerprint_retention_and_ciphertext_tampering_fail(self):
        draft = self.crypto.encrypt(
            retrieval_run_id=self.run, project_id=self.project,
            query_fingerprint=b"q" * 32, plaintext=bytearray(b"query"),
            retention_until=self.until)
        base = RetrievalQueryEnvelope(
            draft.retrieval_run_id, draft.project_id, draft.query_fingerprint,
            draft.encrypted_payload, draft.encryption_metadata,
            draft.key_provider_ref, draft.plaintext_bytes, draft.retention_until)
        changes = (
            {"retrieval_run_id": uuid.uuid4()},
            {"project_id": uuid.uuid4()},
            {"query_fingerprint": b"x" * 32},
            {"retention_until": self.until + timedelta(seconds=1)},
            {"encrypted_payload": draft.encrypted_payload[:-1] + b"x"},
        )
        for change in changes:
            with self.subTest(change=next(iter(change))):
                with self.assertRaises(RetrievalQueryCryptoError):
                    self.crypto.decrypt(replace(base, **change))

    def test_missing_key_and_invalid_plaintext_fail_closed(self):
        crypto = AesGcmRetrievalQueryCrypto(_Keys(), key_ref="missing-key.v1")
        for plaintext in (bytearray(), bytearray(b"query"), bytearray(16385)):
            with self.assertRaises(RetrievalQueryCryptoError):
                crypto.encrypt(
                    retrieval_run_id=self.run, project_id=self.project,
                    query_fingerprint=b"q" * 32, plaintext=plaintext,
                    retention_until=self.until)
            self.assertEqual(plaintext, bytearray(len(plaintext)))

    def test_invalid_key_reference_is_rejected_before_use(self):
        for key_ref in ("", " bad", "x" * 256, "bad key"):
            with self.subTest(key_ref=key_ref), self.assertRaises(ValueError):
                AesGcmRetrievalQueryCrypto(_Keys(), key_ref=key_ref)


if __name__ == "__main__":
    unittest.main()
