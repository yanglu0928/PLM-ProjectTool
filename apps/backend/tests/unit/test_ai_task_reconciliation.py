from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.reconcile_expired_task import (
    AITaskReconciliationError,
    ExpiredAITaskReconciler,
    ReconciledAITaskFailure,
)
from unit.test_ai_suggestion_success import _Actor, _Audit, _Uow


class _Store:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def reconcile_next(self, transaction):
        self.calls.append(transaction)
        return self.result


class ExpiredAITaskReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.result = ReconciledAITaskFailure(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), "RUNNING",
            "AI_PROVIDER_OUTCOME_UNKNOWN", False,
            datetime.now(timezone.utc),
        )

    def test_reconcile_audits_and_commits(self):
        uow, store, audit = _Uow(), _Store(self.result), _Audit()
        service = ExpiredAITaskReconciler(
            unit_of_work=uow, store=store, audit=audit,
            system_actor=_Actor(),
        )
        self.assertEqual(service.reconcile_next(), self.result)
        self.assertTrue(uow.transactions[0].committed)
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_EXECUTION_RECONCILED")
        self.assertEqual(event.reason_code, "AI_PROVIDER_OUTCOME_UNKNOWN")

    def test_empty_scan_does_not_commit_or_audit(self):
        uow, audit = _Uow(), _Audit()
        service = ExpiredAITaskReconciler(
            unit_of_work=uow, store=_Store(None), audit=audit,
            system_actor=_Actor(),
        )
        self.assertIsNone(service.reconcile_next())
        self.assertFalse(uow.transactions[0].committed)
        self.assertEqual(audit.events, [])

    def test_audit_failure_rolls_back(self):
        uow = _Uow()
        service = ExpiredAITaskReconciler(
            unit_of_work=uow, store=_Store(self.result),
            audit=_Audit(fail=True), system_actor=_Actor(),
        )
        with self.assertRaises(AITaskReconciliationError):
            service.reconcile_next()
        self.assertFalse(uow.transactions[0].committed)


if __name__ == "__main__":
    unittest.main()
