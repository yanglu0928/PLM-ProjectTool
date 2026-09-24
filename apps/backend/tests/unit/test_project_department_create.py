from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.create_department import (
    CreateProjectDepartment, ProjectDepartmentCreateError, ProjectDepartmentCreateService,
)
from plm_assistant.modules.project.application.read_departments import DepartmentFacts


class Tx:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.state["commits"] += 1


class Access:
    def __init__(self):
        self.actor = uuid.uuid4()

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor


class Guard:
    def __init__(self):
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1


class AuthFacts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **_kwargs):
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("Department create has no target resource")


class Repo:
    def __init__(self):
        self.facts = None
        self.calls = 0

    def create(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["event"] = event


class ProjectDepartmentCreateTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.project_id = uuid.uuid4()
        self.access, self.guard, self.auth_facts, self.repo = Access(), Guard(), AuthFacts(), Repo()
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.auth_facts,
        )
        self.service = ProjectDepartmentCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repo, audit=Audit(self.state),
        )
        self.command = CreateProjectDepartment(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            "  ＡＢＣ  ", "  研发部  ",
        )
        self.repo.facts = DepartmentFacts(
            uuid.uuid4(), self.project_id, "ABC", "研发部", "ACTIVE",
            datetime.now(timezone.utc), 0,
        )

    def test_normalized_create_audited(self):
        view = self.service.create(self.command)
        self.assertEqual((view.code, view.name, view.etag), ("ABC", "研发部", '"v0"'))
        self.assertEqual(self.repo.kwargs["normalized_code"], "abc")
        self.assertEqual(self.state["event"].action, "PROJECT_DEPARTMENT_CREATED")
        self.assertEqual(self.state["commits"], 1)

    def test_invalid_values_rejected_before_license(self):
        for command in (replace(self.command, code=" "),
                        replace(self.command, code="\x00"),
                        replace(self.command, name=""),
                        replace(self.command, project_id=uuid.UUID(int=0))):
            with self.subTest(command=command):
                with self.assertRaises(ProjectDepartmentCreateError) as caught:
                    self.service.create(command)
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)
        self.assertEqual(self.repo.calls, 0)

    def test_duplicate_fails_without_audit(self):
        self.repo.facts = None
        with self.assertRaises(ProjectDepartmentCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "CONFLICT_DUPLICATE")
        self.assertNotIn("event", self.state)
        self.assertEqual(self.state["commits"], 0)

    def test_non_manager_or_archived_denied(self):
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectDepartmentCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.role = "PROJECT_MANAGER"
        self.auth_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectDepartmentCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repo.calls, 0)

    def test_missing_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectDepartmentCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repo.calls, 0)


if __name__ == "__main__":
    unittest.main()
