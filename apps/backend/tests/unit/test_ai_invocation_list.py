from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationCandidates,
    AIInvocationContextView,
    AIInvocationListService,
    AIInvocationReadError,
    AIInvocationView,
    ListAIInvocations,
)
from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView,
    AITaskView,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def __init__(self, actor, project, role):
        self.actor, self.project, self.role = actor, project, role
    def require_in_transaction(self, *_args, **kwargs):
        return AuthorizedProjectAction(
            self.actor, self.project, kwargs["operation"], self.role,
        )


class Tasks:
    def __init__(self, value): self.value = value
    def get(self, *_args, **_kwargs): return self.value


class Invocations:
    def __init__(self, value): self.value, self.call = value, None
    def list_page(self, _tx, **kwargs):
        self.call = kwargs
        return self.value


class AIInvocationListTests(TestCase):
    def setUp(self) -> None:
        self.actor, self.creator = uuid.uuid4(), uuid.uuid4()
        self.project, self.task_id = uuid.uuid4(), uuid.uuid4()
        self.now = datetime(2026, 10, 3, 13, tzinfo=timezone.utc)
        self.task = AITaskView(
            self.task_id, self.project, "GAP_ANALYSIS", self.creator,
            (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "gap-analysis.v1", 1, uuid.uuid4(), 2,
            "gap-output.v2", "project-documents.v1", uuid.uuid4(),
            "SUCCEEDED", "AVAILABLE", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), None, None, 2, self.now, self.now, self.now,
        )
        context = AIInvocationContextView(
            uuid.uuid4(), 1, "project-documents.v1", "NONE", None, None,
        )
        self.invocation = AIInvocationView(
            uuid.uuid4(), self.task_id, self.project, 2,
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "deepseek-chat-v1",
            uuid.uuid4(), 2, "gap-output.v2", 2, context,
            "SUCCEEDED", "VALID", 100, 20, 350, None, None,
            self.now, self.now, self.now,
        )
        self.query = ListAIInvocations(
            b"s" * 32, uuid.uuid4(), self.project, self.task_id, 10,
        )

    def service(self, *, role="PROJECT_MANAGER", actor=None, task=None,
                candidates=None):
        actor = actor or self.actor
        invocations = Invocations(
            candidates if candidates is not None else
            AIInvocationCandidates((self.invocation,), True),
        )
        service = AIInvocationListService(
            unit_of_work=Tx, access=Access(actor), license_guard=Guard(),
            authorization=Authorization(actor, self.project, role),
            tasks=Tasks(self.task if task is None else task),
            invocations=invocations, clock=lambda: self.now,
        )
        return service, invocations

    def test_creator_or_management_can_list_attempts(self):
        for role, actor in (
            ("PROJECT_MANAGER", self.actor),
            ("CUSTOMER_MANAGER", self.actor),
            ("IMPLEMENTATION_MEMBER", self.creator),
        ):
            with self.subTest(role=role):
                service, repository = self.service(role=role, actor=actor)
                page = service.list(self.query)
                self.assertEqual(page.items, (self.invocation,))
                self.assertEqual(
                    page.next_position,
                    (self.invocation.attempt_no,
                     self.invocation.ai_invocation_id),
                )
                self.assertEqual(repository.call["ai_task_id"], self.task_id)

    def test_noncreator_role_scope_and_cursor_drift_fail_closed(self):
        service, _ = self.service(role="IMPLEMENTATION_MEMBER")
        with self.assertRaises(AIInvocationReadError) as caught:
            service.list(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        service, _ = self.service(role="CUSTOMER_MEMBER")
        with self.assertRaises(AIInvocationReadError):
            service.list(self.query)
        before = (1, uuid.uuid4())
        service, _ = self.service()
        with self.assertRaises(AIInvocationReadError):
            service.list(replace(self.query, before=before))

    def test_context_and_usage_are_bounded(self):
        self.assertEqual(self.invocation.context.mode, "NONE")
        self.assertNotIn("fingerprint", repr(self.invocation))
        with self.assertRaises(AIInvocationReadError):
            replace(self.invocation, latency_ms=-1)


if __name__ == "__main__":
    import unittest
    unittest.main()
