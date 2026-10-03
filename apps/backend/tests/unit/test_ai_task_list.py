from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView,
    AITaskListCandidates,
    AITaskListService,
    AITaskReadError,
    AITaskView,
    ListAITasks,
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


class Repository:
    def __init__(self, page):
        self.page = page
        self.call = None

    def list_page(self, _transaction, **kwargs):
        self.call = kwargs
        return self.page


class AITaskListTests(TestCase):
    def setUp(self) -> None:
        self.actor, self.other = uuid.uuid4(), uuid.uuid4()
        self.project = uuid.uuid4()
        self.now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
        self.first = self._view(uuid.UUID(int=3), self.other, self.now)
        self.second = self._view(
            uuid.UUID(int=2), self.other, self.now - timedelta(seconds=1),
        )
        self.query = ListAITasks(
            b"s" * 32, uuid.uuid4(), self.project, 2,
        )

    def _view(self, task_id, requested_by, requested_at):
        return AITaskView(
            task_id, self.project, "GAP_ANALYSIS", requested_by,
            (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "gap-analysis.v1", 1, uuid.uuid4(), 2,
            "gap-output.v2", "project-documents.v1", uuid.uuid4(),
            "SUCCEEDED", "AVAILABLE", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), None, None, 2, requested_at, requested_at, requested_at,
        )

    def service(self, *, role="PROJECT_MANAGER", actor=None, page=None):
        actor = actor or self.actor
        repository = Repository(
            page if page is not None else AITaskListCandidates(
                (self.first, self.second), True,
            ),
        )
        service = AITaskListService(
            unit_of_work=Tx, access=Access(actor), license_guard=Guard(),
            authorization=Authorization(actor, self.project, role),
            repository=repository, clock=lambda: self.now,
        )
        return service, repository

    def test_management_lists_all_and_returns_stable_next_position(self):
        for role in ("PROJECT_MANAGER", "CUSTOMER_MANAGER"):
            with self.subTest(role=role):
                service, repository = self.service(role=role)
                page = service.list(self.query)
                self.assertEqual(page.items, (self.first, self.second))
                self.assertEqual(
                    page.next_position,
                    (self.second.requested_at, self.second.ai_task_id),
                )
                self.assertIsNone(repository.call["requested_by"])

    def test_implementation_member_is_restricted_to_own_tasks(self):
        own = replace(self.first, requested_by=self.actor)
        service, repository = self.service(
            role="IMPLEMENTATION_MEMBER",
            page=AITaskListCandidates((own,), False),
        )
        page = service.list(self.query)
        self.assertEqual(page.items, (own,))
        self.assertEqual(repository.call["requested_by"], self.actor)
        self.assertIsNone(page.next_position)

    def test_unlisted_role_and_repository_scope_drift_fail_closed(self):
        service, _ = self.service(role="CUSTOMER_MEMBER")
        with self.assertRaises(AITaskReadError) as caught:
            service.list(self.query)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        own = replace(self.first, requested_by=self.actor)
        before = (self.now - timedelta(seconds=5), uuid.UUID(int=99))
        service, _ = self.service(
            role="IMPLEMENTATION_MEMBER",
            page=AITaskListCandidates((own,), False),
        )
        with self.assertRaises(AITaskReadError):
            service.list(replace(self.query, before=before))

    def test_candidate_order_and_page_size_are_bounded(self):
        with self.assertRaises(AITaskReadError):
            AITaskListCandidates((self.second, self.first), False)
        for size in (0, 101):
            with self.assertRaises(AITaskReadError):
                ListAITasks(
                    b"s" * 32, uuid.uuid4(), self.project, size,
                )


if __name__ == "__main__":
    import unittest
    unittest.main()
