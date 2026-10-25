from __future__ import annotations

import unittest
import uuid
from unittest.mock import Mock

from plm_assistant.modules.evidence.application.eligibility_access import EvidenceEligibilityAccessError
from plm_assistant.modules.evidence.application.lookup_eligibility_operation import (
    EvidenceEligibilityLookupError, EvidenceEligibilityOperationLookupService,
    EvidenceEligibilityOperationStatus, LookupEvidenceEligibilityOperation,
)
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult


class _Transaction:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class EligibilityOperationLookupTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.evidence = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.query = LookupEvidenceEligibilityOperation(
            self.actor, b"s" * 32, b"c" * 32, uuid.uuid4(),
            "PROJECT", self.project, self.evidence, "k" * 16,
        )
        self.tx = _Transaction()
        self.access, self.repository, self.receipts, self.guard = (
            Mock(), Mock(), Mock(), Mock())
        self.repository.exists.return_value = True
        self.receipts.lookup_result.return_value = IdempotencyResult(
            "V1_EVIDENCE_ELIGIBILITY", self.evidence, 200)
        self.service = EvidenceEligibilityOperationLookupService(
            unit_of_work=lambda: self.tx, access=self.access,
            evidence=self.repository, receipts=self.receipts,
            license_guard=self.guard,
        )

    def test_completed_is_original_receipt_only_and_never_writes(self):
        self.assertEqual(self.service.lookup(self.query),
                         EvidenceEligibilityOperationStatus("COMPLETED", self.evidence, 200))
        self.guard.require_valid.assert_called_once_with(trace_id=self.query.trace_id)
        self.access.require_in_transaction.assert_called_once_with(
            self.tx, actor_id=self.actor, scope="PROJECT", project_id=self.project,
            operation="V1_EVIDENCE_ELIGIBILITY_OPERATION_LOOKUP",
            session_token=b"s" * 32, csrf_token=b"c" * 32,
        )
        self.repository.exists.assert_called_once_with(
            self.tx, scope="PROJECT", project_id=self.project, evidence_id=self.evidence)
        self.assertEqual(self.receipts.lookup_result.call_args.kwargs["scope"].actor_id, self.actor)
        self.assertEqual(self.receipts.lookup_result.call_args.kwargs["scope"].project_id, self.project)
        self.assertEqual(self.receipts.lookup_result.call_args.kwargs["scope"].operation,
                         "V1_EVIDENCE_SET_ELIGIBILITY")
        self.assertFalse(self.tx.committed)

    def test_missing_receipt_is_not_failed_operation(self):
        self.receipts.lookup_result.return_value = None
        self.assertEqual(self.service.lookup(self.query),
                         EvidenceEligibilityOperationStatus("UNCONFIRMED"))
        self.assertFalse(self.tx.committed)

    def test_current_permission_and_resource_precede_receipt(self):
        self.access.require_in_transaction.side_effect = EvidenceEligibilityAccessError(
            "RESOURCE_NOT_FOUND")
        with self.assertRaises(EvidenceEligibilityLookupError) as caught:
            self.service.lookup(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.repository.exists.assert_not_called()
        self.receipts.lookup_result.assert_not_called()
        self.access.require_in_transaction.side_effect = None
        self.repository.exists.return_value = False
        with self.assertRaises(EvidenceEligibilityLookupError) as caught:
            self.service.lookup(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.receipts.lookup_result.assert_not_called()

    def test_other_evidence_or_bad_receipt_is_never_completed(self):
        for result in (
            IdempotencyResult("V1_EVIDENCE_ELIGIBILITY", uuid.uuid4(), 200),
            IdempotencyResult("V1_OTHER_RESULT", self.evidence, 200),
            IdempotencyResult("V1_EVIDENCE_ELIGIBILITY", self.evidence, 201),
            object(),
        ):
            self.receipts.lookup_result.return_value = result
            with self.subTest(result=result):
                with self.assertRaises(EvidenceEligibilityLookupError) as caught:
                    self.service.lookup(self.query)
                self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")

    def test_bad_key_or_scope_does_not_reach_dependencies(self):
        for query in (
            LookupEvidenceEligibilityOperation(self.actor, b"s" * 32, b"c" * 32,
                uuid.uuid4(), "PROJECT", self.project, self.evidence, "short"),
            LookupEvidenceEligibilityOperation(self.actor, b"s" * 32, b"c" * 32,
                uuid.uuid4(), "PROJECT", None, self.evidence, "k" * 16),
            LookupEvidenceEligibilityOperation(self.actor, b"s" * 32, b"c" * 32,
                uuid.uuid4(), "GLOBAL", self.project, self.evidence, "k" * 16),
        ):
            with self.subTest(query=query):
                with self.assertRaises(EvidenceEligibilityLookupError) as caught:
                    self.service.lookup(query)
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.guard.require_valid.assert_not_called()
        self.access.require_in_transaction.assert_not_called()

    def test_database_error_is_safe_and_no_commit(self):
        self.receipts.lookup_result.side_effect = RuntimeError("private database details")
        with self.assertRaises(EvidenceEligibilityLookupError) as caught:
            self.service.lookup(self.query)
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")
        self.assertFalse(self.tx.committed)


if __name__ == "__main__":
    unittest.main()
