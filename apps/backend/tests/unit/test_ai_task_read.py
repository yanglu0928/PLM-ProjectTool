from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView, AITaskReadError, AITaskReadService, AITaskView, GetAITask,
)
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def __init__(self, actor, project, role): self.actor, self.project, self.role = actor, project, role
    def require_in_transaction(self, *_args, **kwargs):
        return AuthorizedProjectAction(
            self.actor, self.project, kwargs["operation"], self.role,
        )


class Repository:
    def __init__(self, view): self.view = view
    def get(self, *_args, **_kwargs): return self.view


class AITaskReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.requester = uuid.uuid4(), uuid.uuid4()
        self.project, self.task = uuid.uuid4(), uuid.uuid4()
        self.now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.view = AITaskView(
            self.task, self.project, "GAP_ANALYSIS", self.requester,
            (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "gap-analysis.v1", 1, uuid.uuid4(), 2,
            "gap-output.v1", "project-documents.v1", uuid.uuid4(),
            "QUEUED", "NONE", None, uuid.uuid4(), uuid.uuid4(), None, None,
            0, self.now, None, None,
        )
        self.query = GetAITask(b"s" * 32, uuid.uuid4(), self.project, self.task)

    def service(self, *, role="IMPLEMENTATION_MEMBER", actor=None, view=None):
        actor = actor or self.actor
        return AITaskReadService(
            unit_of_work=Tx, access=Access(actor), license_guard=Guard(),
            authorization=Authorization(actor, self.project, role),
            repository=Repository(self.view if view is None else view),
            clock=lambda: self.now,
        )

    def test_requester_and_project_management_roles_can_read(self):
        requester = self.service(actor=self.requester).get(self.query)
        manager = self.service(role="PROJECT_MANAGER").get(self.query)
        customer_manager = self.service(role="CUSTOMER_MANAGER").get(self.query)
        self.assertEqual((requester, manager, customer_manager),
                         (self.view, self.view, self.view))

    def test_non_requesting_ordinary_member_and_missing_task_are_hidden(self):
        for service in (
            self.service(role="IMPLEMENTATION_MEMBER"),
            self.service(role="CUSTOMER_MEMBER"),
            self.service(role="PROJECT_MANAGER", view=False),
        ):
            with self.subTest(service=service):
                with self.assertRaises(AITaskReadError) as caught:
                    service.get(self.query)
                self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
