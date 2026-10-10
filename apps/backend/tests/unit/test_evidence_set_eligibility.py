from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.read_documents import DocumentEvidenceSourceFacts
from plm_assistant.modules.evidence.application.eligibility_record import LockedEvidenceEligibility
from plm_assistant.modules.evidence.application.set_eligibility import (
    EvidenceEligibilityCommandError, EvidenceEligibilityService, SetEvidenceEligibility,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        self.committed = True


class _Access:
    def __init__(self):
        self.calls = 0

    def require_in_transaction(self, tx, **kwargs):
        self.calls += 1
        assert kwargs["session_token"] == b"s" * 32
        assert kwargs["csrf_token"] == b"c" * 32


class _Source:
    category = "PROJECT_RECORD"
    unavailable = False

    def get_source_facts_for_evidence(self, tx, query, document_id, version_id):
        if self.unavailable:
            from plm_assistant.modules.document.application.read_documents import DocumentReadError
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        return DocumentEvidenceSourceFacts(
            document_id, version_id, query.scope, query.project_id,
            self.category, "ACTIVE", "a" * 64,
        )


class _Repository:
    def __init__(self, locked):
        self.locked = locked
        self.decisions = 0

    def lock(self, tx, **kwargs):
        return self.locked

    def decide(self, tx, *, locked, state, reason, actor_id):
        self.decisions += 1
        assert locked is self.locked
        self.locked = replace(locked, eligibility_state=state,
                              eligibility_reason=reason,
                              lock_version=locked.lock_version + 1)
        return self.locked.lock_version


class _Receipts:
    def __init__(self):
        self.result = None
        self.completed = 0
        self.fingerprint = None

    def reserve(self, tx, *, scope, request_fingerprint):
        if self.fingerprint is not None and self.fingerprint != request_fingerprint:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.fingerprint = request_fingerprint
        return self.result

    def complete(self, tx, *, scope, result):
        self.result = result
        self.completed += 1


class _Guard:
    valid = True

    def require_valid(self, *, trace_id):
        if not self.valid:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class _Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, draft):
        if self.fail:
            raise RuntimeError("synthetic audit unavailable")
        self.events.append(draft)


class EvidenceSetEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.evidence = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.document, self.version = uuid.uuid4(), uuid.uuid4()
        self.command = SetEvidenceEligibility(
            self.actor, b"s" * 32, b"c" * 32, uuid.uuid4(), "PROJECT",
            self.project, self.evidence, 0, "ELIGIBLE", "已人工核对实际调研记录",
        )
        self.tx = _Tx()
        self.access, self.source = _Access(), _Source()
        self.repository = _Repository(LockedEvidenceEligibility(
            self.evidence, "PROJECT", self.project, self.document,
            self.version, b"a" * 32, "CANDIDATE", 0,
        ))
        self.receipts, self.guard, self.audit = _Receipts(), _Guard(), _Audit()
        self.service = EvidenceEligibilityService(
            unit_of_work=lambda: self.tx, access=self.access,
            source_facts=self.source, repository=self.repository,
            receipts=self.receipts, license_guard=self.guard, audit=self.audit,
        )

    def test_first_decision_commits_audit_and_receipt_once(self):
        result = self.service.set(self.command, idempotency_key="a" * 16)
        self.assertEqual((result.eligibility_state, result.etag), ("ELIGIBLE", '"v1"'))
        self.assertTrue(self.tx.committed)
        self.assertEqual((self.repository.decisions, self.receipts.completed,
                          len(self.audit.events)), (1, 1, 1))
        self.assertEqual(self.audit.events[0].after_state, "ELIGIBLE")
        self.assertEqual(self.receipts.result,
                         IdempotencyResult("V1_EVIDENCE_ELIGIBILITY", self.evidence, 200))

    def test_exact_replay_does_not_redecide_or_reaudit(self):
        first = self.service.set(self.command, idempotency_key="a" * 16)
        self.tx = _Tx()
        again = self.service.set(self.command, idempotency_key="a" * 16)
        self.assertEqual(first, again)
        self.assertEqual((self.repository.decisions, self.receipts.completed,
                          len(self.audit.events)), (1, 1, 1))
        self.assertEqual(self.access.calls, 2)
        with self.assertRaises(EvidenceEligibilityCommandError) as caught:
            self.service.set(replace(self.command, reason="其他理由"),
                             idempotency_key="a" * 16)
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")

    def test_template_and_unavailable_source_fail_before_write(self):
        self.source.category = "TEMPLATE"
        with self.assertRaises(EvidenceEligibilityCommandError) as caught:
            self.service.set(self.command, idempotency_key="a" * 16)
        self.assertEqual(caught.exception.code, "CONFLICT_STATE")
        self.source.category, self.source.unavailable = "PROJECT_RECORD", True
        with self.assertRaises(EvidenceEligibilityCommandError) as caught:
            self.service.set(self.command, idempotency_key="a" * 16)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual((self.repository.decisions, len(self.audit.events)), (0, 0))

    def test_version_and_license_fail_closed(self):
        with self.assertRaises(EvidenceEligibilityCommandError) as caught:
            self.service.set(replace(self.command, expected_version=1),
                             idempotency_key="a" * 16)
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        self.guard.valid = False
        with self.assertRaises(EvidenceEligibilityCommandError) as caught:
            self.service.set(self.command, idempotency_key="b" * 16)
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.assertEqual(self.repository.decisions, 0)

    def test_audit_failure_prevents_commit(self):
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.service.set(self.command, idempotency_key="a" * 16)
        self.assertFalse(self.tx.committed)
        self.assertEqual(self.receipts.completed, 0)


if __name__ == "__main__":
    unittest.main()
