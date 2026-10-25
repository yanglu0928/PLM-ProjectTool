from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.cancel_task_execution import (
    AITaskCancellationError,
    AITaskCancellationOwner,
    CancelAITaskExecution,
    CancelledAITaskExecution,
)
from plm_assistant.modules.ai.application.request_task_cancel import (
    AITaskCancellationBinding,
    AITaskJobCancelOwner,
)
from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError,
    RequestProjectJobCancel,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from unit.test_ai_suggestion_success import _Audit, _Uow


class _Store:
    def __init__(self, result):
        self.result, self.calls = result, []

    def cancel(self, transaction, *, command):
        self.calls.append((transaction, command))
        return self.result


class _OwnerStore:
    def __init__(self, binding, result):
        self._binding, self._result = binding, result

    def binding(self, *_args, **_kwargs):
        return self._binding

    def cancel(self, *_args, **_kwargs):
        return self._result

    def receipt(self, *_args, **_kwargs):
        return self._result


class _Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor


class _Projects:
    def __init__(self, actor, project, role):
        self.proof = AuthorizedProjectAction(
            actor, project, "JOB_PROJECT_CANCEL", role,
        )

    def require_in_transaction(self, *_args, **_kwargs):
        return self.proof


class _Guard:
    def require_valid(self, **_kwargs):
        return object()


class _Receipts:
    def __init__(self):
        self.completed = []

    def reserve(self, *_args, **_kwargs):
        return None

    def complete(self, transaction, *, scope, result):
        self.completed.append((transaction, scope, result))


class AITaskCancellationTests(unittest.TestCase):
    def setUp(self):
        self.command = CancelAITaskExecution(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 2,
            "用户不再需要本次建议",
        )

    def _result(self, *, crossed=False):
        return CancelledAITaskExecution(
            self.command.ai_task_id, uuid.uuid4(), uuid.uuid4(),
            self.command.project_id,
            "FAILED" if crossed else "CANCELLED", True, crossed,
            "AI_PROVIDER_OUTCOME_UNKNOWN" if crossed else None, 3, 8,
            datetime.now(timezone.utc),
        )

    def test_pre_send_cancel_audits_and_commits(self):
        uow, audit = _Uow(), _Audit()
        result = self._result()
        owner = AITaskCancellationOwner(
            unit_of_work=uow, store=_Store(result), audit=audit,
        )
        self.assertEqual(owner.cancel(self.command), result)
        self.assertTrue(uow.transactions[0].committed)
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_CANCELLED")
        self.assertEqual(event.outcome, "SUCCESS")
        self.assertEqual(event.before_state, "RUNNING")

    def test_post_fence_cancel_is_unknown_failure(self):
        uow, audit = _Uow(), _Audit()
        result = self._result(crossed=True)
        owner = AITaskCancellationOwner(
            unit_of_work=uow, store=_Store(result), audit=audit,
        )
        self.assertEqual(owner.cancel(self.command), result)
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_CANCEL_OUTCOME_UNKNOWN")
        self.assertEqual(event.outcome, "FAILED")

    def test_audit_failure_rolls_back(self):
        uow = _Uow()
        owner = AITaskCancellationOwner(
            unit_of_work=uow, store=_Store(self._result()),
            audit=_Audit(fail=True),
        )
        with self.assertRaises(AITaskCancellationError):
            owner.cancel(self.command)
        self.assertFalse(uow.transactions[0].committed)

    def test_terminal_check_audits_actual_terminal_before_state(self):
        uow, audit = _Uow(), _Audit()
        result = CancelledAITaskExecution(
            self.command.ai_task_id, uuid.uuid4(), uuid.uuid4(),
            self.command.project_id, "FAILED", False, False,
            "AI_PROVIDER_RESPONSE_INVALID", 3, 8,
            datetime.now(timezone.utc),
        )
        owner = AITaskCancellationOwner(
            unit_of_work=uow, store=_Store(result), audit=audit,
        )
        self.assertEqual(owner.cancel(self.command), result)
        event = audit.events[0][1]
        self.assertEqual(event.action, "AI_TASK_CANCEL_CHECKED")
        self.assertEqual((event.before_state, event.after_state),
                         ("FAILED", "FAILED"))

    def _job_owner(self, *, crossed=False, role="IMPLEMENTATION_MEMBER",
                   same_actor=True):
        actor, creator, project = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        if same_actor:
            creator = actor
        task, job, invocation = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        binding = AITaskCancellationBinding(task, job, project, creator, 4, 7)
        result = CancelledAITaskExecution(
            task, invocation, job, project,
            "FAILED" if crossed else "CANCELLED", True, crossed,
            "AI_PROVIDER_OUTCOME_UNKNOWN" if crossed else None,
            5, 8, datetime.now(timezone.utc),
        )
        uow, receipts = _Uow(), _Receipts()
        service = AITaskJobCancelOwner(
            unit_of_work=uow, store=_OwnerStore(binding, result),
            session_access=_Access(actor),
            projects=_Projects(actor, project, role), license_guard=_Guard(),
            receipts=receipts, audit=_Audit(),
        )
        command = RequestProjectJobCancel(
            job, project, b"s" * 32, b"c" * 32, uuid.uuid4(),
            "用户取消", 7,
        )
        return service, command, uow, receipts

    def test_job_owner_preserves_safe_cancel_changed_receipt(self):
        service, command, uow, receipts = self._job_owner()
        result = service.cancel(
            command, idempotency_key="1234567890abcdef",
        )
        self.assertEqual((result.state, result.changed, result.lock_version),
                         ("CANCELLED", True, 8))
        self.assertTrue(uow.transactions[0].committed)
        self.assertIsInstance(receipts.completed[0][2], IdempotencyResult)

    def test_job_owner_reports_post_fence_unknown_as_not_cancelled(self):
        service, command, _, _ = self._job_owner(crossed=True)
        result = service.cancel(
            command, idempotency_key="1234567890abcdef",
        )
        self.assertEqual((result.state, result.changed), ("FAILED", False))

    def test_job_owner_denies_non_creator_non_manager(self):
        service, command, _, receipts = self._job_owner(same_actor=False)
        with self.assertRaises(JobCancelError) as caught:
            service.cancel(command, idempotency_key="1234567890abcdef")
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertFalse(receipts.completed)


if __name__ == "__main__":
    unittest.main()
