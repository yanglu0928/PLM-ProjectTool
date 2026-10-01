from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import DocumentVersionView
from plm_assistant.modules.evidence.application.create_evidence import (
    CreateEvidence, EvidenceCreateError, EvidenceCreateService,
)
from plm_assistant.modules.evidence.application.document_source_proof import EvidenceDocumentProof
from plm_assistant.modules.evidence.application.parsed_node_proof import EvidenceParsedNodeProof
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Tx:
    def __init__(self, state):
        self.state = state
        self.committed = False

    def __enter__(self):
        self.state.transactions.append(self)
        return self

    def __exit__(self, *_):
        if not self.committed:
            self.state.pending = None

    def commit(self):
        self.committed = True
        if self.state.pending is not None:
            self.state.stored = self.state.pending
            self.state.pending = None


class _State:
    def __init__(self):
        self.transactions = []
        self.access_calls = 0
        self.denied_on = None
        self.pending = None
        self.stored = None
        self.audit_calls = 0
        self.fail_audit = False
        self.version_sha = b"a" * 32

    def require_in_transaction(self, *_args, **_kwargs):
        self.access_calls += 1
        if self.access_calls == self.denied_on:
            raise EvidenceCreateError("AUTH_ACCESS_DENIED")

    def get_version_for_trace(self, _tx, _query, document_id, version_id):
        return DocumentVersionView(version_id, document_id, 1, self.version_sha.hex(),
                                   10, "text/plain", "AVAILABLE", None,
                                   datetime(2026, 10, 1, tzinfo=timezone.utc), None)

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.fingerprint = request_fingerprint
        if self.stored is None:
            return None
        if self.stored[1] != request_fingerprint:
            raise EvidenceCreateError("CONFLICT_IDEMPOTENCY")
        return IdempotencyResult("V1_EVIDENCE", self.stored[0], 201)

    def complete(self, _tx, *, scope, result):
        self.pending = (result.ref_id, self.fingerprint)

    def create(self, _tx, *, command, locator, fingerprint):
        return uuid.uuid4(), datetime(2026, 10, 1, tzinfo=timezone.utc)

    def replay(self, _tx, evidence_id, *, command, locator, fingerprint):
        return datetime(2026, 10, 1, tzinfo=timezone.utc)

    def append(self, _tx, event):
        self.audit_calls += 1
        if self.fail_audit:
            raise RuntimeError("audit failed")
        return uuid.uuid4()


class _DocumentProof:
    def __init__(self, state):
        self.state = state

    def prove(self, _query, *, document_id, document_version_id, locator):
        return EvidenceDocumentProof(document_version_id, locator, self.state.version_sha)


class _NodeProof:
    def __init__(self, state):
        self.state = state

    def prove(self, _query, *, document_id, document_version_id, parse_record_id, locator):
        return EvidenceParsedNodeProof(document_version_id, parse_record_id,
                                       "line:1", locator, b"b" * 32,
                                       source_sha256=self.state.version_sha)


class EvidenceCreateServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = _State()
        self.actor = uuid.uuid4()
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()
        self.version = uuid.uuid4()
        self.command = CreateEvidence(
            self.actor, b"s" * 32, b"c" * 32, uuid.uuid4(), "PROJECT",
            self.project, self.document, self.version,
            {"locator_type": "DOCUMENT"}, "全文",
        )
        self.key = "evidence-create-001"
        self.service = EvidenceCreateService(
            unit_of_work=lambda: _Tx(self.state), access=self.state,
            versions=self.state, document_proof=_DocumentProof(self.state),
            node_proof=_NodeProof(self.state), repository=self.state,
            receipts=self.state, audit=self.state,
        )

    def test_create_and_replay_do_not_repeat_audit(self):
        first = self.service.create(self.command, idempotency_key=self.key)
        second = self.service.create(self.command, idempotency_key=self.key)
        self.assertEqual(first, second)
        self.assertEqual(first.eligibility_state, "CANDIDATE")
        self.assertEqual(self.state.audit_calls, 1)
        self.assertEqual(len(self.state.transactions), 4)
        self.assertEqual(sum(tx.committed for tx in self.state.transactions), 1)

    def test_recheck_denial_prevents_insert(self):
        self.state.denied_on = 2
        with self.assertRaisesRegex(EvidenceCreateError, "AUTH_ACCESS_DENIED"):
            self.service.create(self.command, idempotency_key=self.key)
        self.assertIsNone(self.state.stored)
        self.assertEqual(self.state.audit_calls, 0)

    def test_audit_failure_rolls_back_receipt_and_evidence(self):
        self.state.fail_audit = True
        with self.assertRaisesRegex(RuntimeError, "audit failed"):
            self.service.create(self.command, idempotency_key=self.key)
        self.assertIsNone(self.state.stored)
        self.assertIsNone(self.state.pending)

    def test_node_source_drift_fails_closed(self):
        parse_id = uuid.uuid4()
        command = CreateEvidence(
            self.actor, b"s" * 32, b"c" * 32, uuid.uuid4(), "PROJECT",
            self.project, self.document, self.version,
            {"locator_type": "SECTION", "section_path": "word/heading/1/1"},
            "第一章", parse_record_id=parse_id,
        )
        self.state.version_sha = b"a" * 32
        original = self.state.get_version_for_trace

        def drift(*args):
            view = original(*args)
            return DocumentVersionView(view.document_version_id, view.document_id,
                                       view.version_no, (b"z" * 32).hex(), view.size_bytes,
                                       view.detected_mime, view.availability_state,
                                       view.supersedes_version_ref, view.created_at,
                                       view.integrity_checked_at)

        self.state.get_version_for_trace = drift
        with self.assertRaisesRegex(EvidenceCreateError, "EVIDENCE_FINGERPRINT_MISMATCH"):
            self.service.create(command, idempotency_key=self.key)
        self.assertEqual(self.state.audit_calls, 0)

    def test_validation_rejects_unproven_locator_and_key(self):
        with self.assertRaisesRegex(EvidenceCreateError, "VALIDATION_FAILED"):
            self.service.create(self.command, idempotency_key="short")
        bad = CreateEvidence(
            self.actor, b"s" * 32, b"c" * 32, uuid.uuid4(), "PROJECT",
            self.project, self.document, self.version,
            {"locator_type": "SECTION", "section_path": "x"}, "bad",
        )
        with self.assertRaisesRegex(EvidenceCreateError, "VALIDATION_FAILED"):
            self.service.create(bad, idempotency_key=self.key)


if __name__ == "__main__":
    unittest.main()
