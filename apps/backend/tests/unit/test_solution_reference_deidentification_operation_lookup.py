from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.lookup_reference_deidentification_operation import (
    LookupReferenceDeidentificationOperation, ReferenceDeidentificationLookupError,
    ReferenceDeidentificationOperationLookupService,
)


ACTOR, CONFIRMATION, TRACE = (uuid.uuid4() for _ in range(3))


class Access:
    def __init__(self): self.actor = ACTOR
    def authorized_admin(self, transaction, *, session_token, csrf_token, now):
        return self.actor


class Guard:
    denied = False
    def require_valid(self, *, trace_id):
        if self.denied:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
        return object()


class Receipts:
    def __init__(self): self.result = None; self.scopes = []
    def lookup_result(self, transaction, *, scope):
        self.scopes.append(scope); return self.result


class Confirmations:
    def __init__(self): self.state = "CONFIRMED"; self.calls = []
    def current_state(self, transaction, *, confirmation_id, actor_id, now):
        self.calls.append((confirmation_id, actor_id)); return self.state


@contextmanager
def unit_of_work(): yield object()


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.access, self.receipts, self.confirmations = Access(), Receipts(), Confirmations()
        self.guard = Guard()
        self.service = ReferenceDeidentificationOperationLookupService(
            unit_of_work=unit_of_work, access=self.access, license_guard=self.guard,
            receipts=self.receipts, confirmations=self.confirmations,
            clock=lambda: datetime(2026, 10, 9, tzinfo=timezone.utc))
        self.query = LookupReferenceDeidentificationOperation(
            b"s" * 32, b"c" * 32, TRACE, "CONFIRM", "k" * 16)

    def test_missing_receipt_is_inconclusive_and_no_state_read(self):
        result = self.service.lookup(self.query)
        self.assertEqual("UNCONFIRMED", result.status)
        self.assertIsNone(result.confirmation_id)
        self.assertFalse(self.confirmations.calls)

    def test_confirm_and_revoke_receipts_are_actor_scoped(self):
        self.receipts.result = IdempotencyResult(
            "V1_SOL_REFERENCE_DEIDENTIFICATION", CONFIRMATION, 201)
        result = self.service.lookup(self.query)
        self.assertEqual(("COMPLETED", CONFIRMATION, 201, "CONFIRMED"),
                         (result.status, result.confirmation_id,
                          result.first_status_code, result.current_state))
        self.assertEqual(ACTOR, self.receipts.scopes[-1].actor_id)
        self.assertIsNone(self.receipts.scopes[-1].project_id)
        self.confirmations.state = "REVOKED"
        revoked = self.service.lookup(self.query)
        self.assertEqual("REVOKED", revoked.current_state)
        self.receipts.result = IdempotencyResult(
            "V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKED", CONFIRMATION, 200)
        revoke = self.service.lookup(LookupReferenceDeidentificationOperation(
            b"s" * 32, b"c" * 32, TRACE, "REVOKE", "k" * 16))
        self.assertEqual((200, "REVOKED"), (revoke.first_status_code, revoke.current_state))

    def test_access_and_receipt_mismatch_fail_closed(self):
        self.access.actor = None
        with self.assertRaisesRegex(ReferenceDeidentificationLookupError, "AUTH_ACCESS_DENIED"):
            self.service.lookup(self.query)
        self.assertFalse(self.receipts.scopes)
        self.access.actor = ACTOR
        self.receipts.result = IdempotencyResult("V1_WRONG", CONFIRMATION, 201)
        with self.assertRaisesRegex(ReferenceDeidentificationLookupError, "CONFLICT_IDEMPOTENCY"):
            self.service.lookup(self.query)
        self.receipts.result = IdempotencyResult(
            "V1_SOL_REFERENCE_DEIDENTIFICATION", CONFIRMATION, 201)
        self.confirmations.state = None
        with self.assertRaisesRegex(ReferenceDeidentificationLookupError, "SOLUTION_UNAVAILABLE"):
            self.service.lookup(self.query)

    def test_invalid_operation_is_rejected_before_io(self):
        with self.assertRaisesRegex(ReferenceDeidentificationLookupError, "VALIDATION_FAILED"):
            self.service.lookup(LookupReferenceDeidentificationOperation(
                b"s" * 32, b"c" * 32, TRACE, "DELETE", "k" * 16))
        self.assertFalse(self.receipts.scopes)

    def test_license_denied_without_receipt_access(self):
        self.guard.denied = True
        with self.assertRaisesRegex(ReferenceDeidentificationLookupError, "LICENSE_OPERATION_DENIED"):
            self.service.lookup(self.query)
        self.assertFalse(self.receipts.scopes)


if __name__ == "__main__": unittest.main()
