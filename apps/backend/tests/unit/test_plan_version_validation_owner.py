from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone

from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionSourceProofError,
)
from plm_assistant.modules.plan.application.plan_version_input import (
    FixedVersionRef,
)
from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProof,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionSnapshotView,
)
from plm_assistant.modules.plan.application.validate_plan_version import (
    PlanVersionValidationError, PlanVersionValidationService, ValidatePlanVersion,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionValidationReport,
)


PROJECT, PLAN, VERSION, ACTOR = (uuid.uuid4() for _ in range(4))
OUTLINE, OUTLINE_VERSION, ITEM = (uuid.uuid4() for _ in range(3))
NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
KEY = "plan-validation-key-0001"


class _Uow(AbstractContextManager):
    def __init__(self, transactions):
        self.transactions = transactions

    def __enter__(self):
        self.tx = _Transaction()
        self.transactions.append(self.tx)
        return self.tx

    def __exit__(self, *_):
        return False


class _Transaction:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class _Access:
    def __init__(self):
        self.actor = ACTOR

    def authenticated_user(self, transaction, **_):
        return self.actor


class _License:
    def require_valid(self, **_):
        return True


class _Authorization:
    def __init__(self):
        self.denied = False
        self.calls = []

    def require_in_transaction(self, transaction, *, user_id, project_id, operation):
        self.calls.append((user_id, project_id, operation))
        if self.denied:
            from plm_assistant.modules.project.application.authorization import (
                ProjectAuthorizationError,
            )
            raise ProjectAuthorizationError("AUTH_ACCESS_DENIED")
        return type("Authorized", (), {
            "user_id": user_id, "project_id": project_id, "operation": operation,
        })()


class _Snapshots:
    def __init__(self, view):
        self.view = view

    def get_current(self, *_args, **_kwargs):
        return self.view


class _SolutionProof:
    def __init__(self):
        self.fail = False
        self.calls = 0

    def prove(self, *_args, **_kwargs):
        self.calls += 1
        if self.fail:
            from plm_assistant.modules.plan.application.prove_approved_solution_input import (
                ApprovedSolutionInputProofError,
            )
            raise ApprovedSolutionInputProofError()
        return ApprovedSolutionInputProof(
            PROJECT, OUTLINE, OUTLINE_VERSION, b"o" * 32, (), (), b"r" * 32)


class _SourceProof:
    def __init__(self):
        self.fail = False

    def validate(self, *_args, **_kwargs):
        if self.fail:
            raise PlanVersionSourceProofError()


class _Results:
    def __init__(self):
        self.rows = {}
        self.fail_save = False

    def get(self, _tx, *, audit_event_id, **_):
        return self.rows.get(audit_event_id)

    def save(self, _tx, *, audit_event_id, report, **_):
        if self.fail_save:
            raise RuntimeError("synthetic report insert failure")
        self.rows[audit_event_id] = report


class _Receipts:
    def __init__(self):
        self.rows = {}
        self.fail_complete = False

    def reserve(self, _tx, *, scope, request_fingerprint):
        key = (scope.actor_id, scope.project_id, scope.operation, scope.key_digest)
        current = self.rows.get(key)
        if current is None:
            self.pending = (key, request_fingerprint)
            return None
        fingerprint, result = current
        if fingerprint != request_fingerprint:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return result

    def complete(self, _tx, *, scope, result):
        if self.fail_complete:
            raise RuntimeError("synthetic receipt completion failure")
        key = (scope.actor_id, scope.project_id, scope.operation, scope.key_digest)
        self.rows[key] = (self.pending[1], result)


class _Audit:
    def __init__(self):
        self.rows = []
        self.fail = False

    def append(self, _tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.rows.append(event)
        return uuid.uuid4()


def _view() -> PlanVersionSnapshotView:
    solution = {
        "resource_kind": "OUTLINE", "resource_id": str(OUTLINE),
        "version_id": str(OUTLINE_VERSION), "spec_series_id": None,
        "spec_type": None,
    }
    item = {
        "wbs_item_id": str(ITEM), "parent_item_id": None,
        "wbs_code": "WBS-1", "name": "实施", "level": 1,
        "category": "IMPLEMENTATION", "owner_ref": None,
        "support_role_refs": ["PROJECT_MANAGER"],
        "planned_start": "2026-10-01", "planned_finish": "2026-10-03",
        "duration_minutes": 120, "actual_start": None, "actual_finish": None,
        "item_state": "NOT_STARTED", "entry_conditions": ["来源已批准"],
        "acceptance_criteria": ["通过验证"], "requirement_refs": [],
        "solution_refs": [solution], "prototype_refs": [], "evidence_refs": [],
        "output_refs": [], "risk": None, "explicit_exclusion": None,
    }
    return PlanVersionSnapshotView(
        VERSION, PLAN, PROJECT, 1, "DRAFT", ACTOR, NOW, None, None, None,
        {"calendar_ref": "CN_WORKDAY", "approved_solution_refs": [solution],
         "wbs_items": [item], "dependencies": [], "milestones": [], "exclusions": []})


class PlanVersionValidationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.transactions = []
        self.access, self.authorization = _Access(), _Authorization()
        self.solution, self.source, self.results = _SolutionProof(), _SourceProof(), _Results()
        self.receipts, self.audit = _Receipts(), _Audit()
        self.service = PlanVersionValidationService(
            unit_of_work=lambda: _Uow(self.transactions), access=self.access,
            license_guard=_License(), authorization=self.authorization,
            snapshots=_Snapshots(_view()), results=self.results,
            solution_proof=self.solution, source_proofs=self.source,
            receipts=self.receipts, audit=self.audit, clock=lambda: NOW)
        self.command = ValidatePlanVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, PLAN, VERSION, KEY)

    def test_success_and_same_key_replay_return_exact_first_report(self):
        first = self.service.validate(self.command)
        second = self.service.validate(self.command)
        self.assertEqual(first, second)
        self.assertTrue(first.valid)
        self.assertEqual(1, len(self.audit.rows))
        self.assertEqual(1, len(self.results.rows))
        self.assertEqual(1, self.solution.calls)
        self.assertEqual(2, len(self.transactions))
        self.assertEqual([1, 1], [tx.commits for tx in self.transactions])
        self.assertEqual("PLAN_VERSION_VALIDATE", self.authorization.calls[0][2])

    def test_source_loss_is_a_persisted_blocking_report(self):
        self.solution.fail = True
        report = self.service.validate(self.command)
        self.assertFalse(report.valid)
        self.assertIn("APPROVED_SOURCE_UNAVAILABLE", report.blocking_issues)
        self.assertEqual(1, len(self.audit.rows))
        self.assertEqual(1, len(self.results.rows))

    def test_rejection_does_not_create_audit_result_or_receipt(self):
        self.authorization.denied = True
        with self.assertRaises(PlanVersionValidationError) as caught:
            self.service.validate(self.command)
        self.assertEqual("AUTH_ACCESS_DENIED", caught.exception.code)
        self.assertEqual([], self.audit.rows)
        self.assertEqual({}, self.results.rows)
        self.assertEqual({}, self.receipts.rows)

    def test_audit_failure_leaves_no_completed_report_or_receipt(self):
        self.audit.fail = True
        with self.assertRaises(PlanVersionValidationError):
            self.service.validate(self.command)
        self.assertEqual({}, self.results.rows)
        self.assertEqual({}, self.receipts.rows)
        self.assertEqual(0, self.transactions[0].commits)

    def test_receipt_completion_failure_does_not_commit_report(self):
        self.receipts.fail_complete = True
        with self.assertRaises(PlanVersionValidationError):
            self.service.validate(self.command)
        self.assertEqual(1, len(self.audit.rows))
        self.assertEqual(1, len(self.results.rows))
        self.assertEqual({}, self.receipts.rows)
        self.assertEqual(0, self.transactions[0].commits)


if __name__ == "__main__":
    unittest.main()
