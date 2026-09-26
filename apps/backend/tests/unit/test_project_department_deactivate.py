from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.deactivate_department import (
    DeactivateProjectDepartment, ProjectDepartmentDeactivateError,
    ProjectDepartmentDeactivateService,
)
from plm_assistant.modules.project.application.read_departments import DepartmentFacts
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


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
    def __init__(self, project_id):
        self.owner = project_id
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **_kwargs):
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, _tx, **_kwargs):
        return self.owner


class Repo:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def deactivate(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts

    def save_deactivate_result(self, _tx, *, result_id, project_id, view, version):
        self.snapshot = (result_id, project_id, view, version)

    def get_deactivate_result(self, _tx, *, result_id, project_id, department_id):
        saved_id, saved_project, view, _ = self.snapshot
        return view if (saved_id, saved_project, view.department_id) == (
            result_id, project_id, department_id,
        ) else None


class Receipts:
    def __init__(self):
        self.saved = None

    def reserve(self, _tx, *, scope, request_fingerprint):
        self.fingerprint = request_fingerprint
        if self.saved is None:
            return None
        saved_scope, saved_fingerprint, result = self.saved
        if scope != saved_scope or request_fingerprint != saved_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return result

    def complete(self, _tx, *, scope, result):
        self.saved = (scope, self.fingerprint, result)


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["event"] = event


class ProjectDepartmentDeactivateTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.project_id, self.department_id = uuid.uuid4(), uuid.uuid4()
        self.access, self.guard = Access(), Guard()
        self.auth_facts = AuthFacts(self.project_id)
        self.repo = Repo(DepartmentFacts(
            self.department_id, self.project_id, "D1", "部门",
            "INACTIVE", datetime.now(timezone.utc), 1,
        ))
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.auth_facts,
        )
        self.service = ProjectDepartmentDeactivateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repo, audit=Audit(self.state),
        )
        self.command = DeactivateProjectDepartment(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            self.department_id, 0,
        )
        self.receipts = Receipts()
        self.service._receipts = self.receipts

    def test_deactivation_is_audited(self):
        view = self.service.deactivate(self.command)
        self.assertEqual((view.state, view.etag), ("INACTIVE", '"v1"'))
        self.assertEqual(self.state["event"].action, "PROJECT_DEPARTMENT_DEACTIVATED")
        self.assertEqual(self.state["event"].before_state, "ACTIVE")
        self.assertEqual(self.state["event"].after_state, "INACTIVE")
        self.assertEqual(self.state["commits"], 1)

    def test_invalid_command_before_license(self):
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(replace(self.command, expected_version=-1))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_non_manager_cross_project_archived_denied(self):
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.role = "PROJECT_MANAGER"
        self.auth_facts.owner = uuid.uuid4()
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.owner = self.project_id
        self.auth_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repo.calls, 0)

    def test_missing_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")

    def test_bad_repository_projection_rolls_back(self):
        self.repo.facts = None
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.assertEqual(self.state["commits"], 0)

    def test_idempotent_replay_keeps_first_result_and_rechecks_access(self):
        first = self.service.deactivate_idempotent(
            self.command, idempotency_key="department-deactivate-key-001",
        )
        self.repo.facts = replace(self.repo.facts, name="Changed after first result")
        replay = self.service.deactivate_idempotent(
            self.command, idempotency_key="department-deactivate-key-001",
        )
        self.assertEqual(first, replay)
        self.assertEqual(self.repo.calls, 1)
        self.assertEqual(self.state["commits"], 1)
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate_idempotent(
                replace(self.command, expected_version=1),
                idempotency_key="department-deactivate-key-001",
            )
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectDepartmentDeactivateError) as caught:
            self.service.deactivate_idempotent(
                self.command, idempotency_key="department-deactivate-key-001",
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
