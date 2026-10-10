from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.patch_department import (
    PatchProjectDepartment, ProjectDepartmentPatchError, ProjectDepartmentPatchService,
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
        self.changed = True
        self.calls = 0

    def patch(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts, self.changed


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["event"] = event


class ProjectDepartmentPatchTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.project_id, self.department_id = uuid.uuid4(), uuid.uuid4()
        self.access, self.guard = Access(), Guard()
        self.auth_facts = AuthFacts(self.project_id)
        self.repo = Repo(DepartmentFacts(
            self.department_id, self.project_id, "ABC", "新部门",
            "ACTIVE", datetime.now(timezone.utc), 1,
        ))
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.auth_facts,
        )
        self.service = ProjectDepartmentPatchService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repo, audit=Audit(self.state),
        )
        self.command = PatchProjectDepartment(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            self.department_id, 0, code="  ＡＢＣ  ", name="  新部门  ",
        )

    def test_normalized_patch_audited(self):
        view = self.service.patch(self.command)
        self.assertEqual((view.code, view.name, view.etag), ("ABC", "新部门", '"v1"'))
        self.assertEqual(self.repo.kwargs["normalized_code"], "abc")
        self.assertEqual(self.state["event"].action, "PROJECT_DEPARTMENT_PATCHED")
        self.assertEqual(self.state["commits"], 1)

    def test_noop_does_not_emit_audit(self):
        self.repo.changed = False
        self.service.patch(self.command)
        self.assertNotIn("event", self.state)

    def test_invalid_values_rejected_before_license(self):
        for command in (replace(self.command, code=None, name=None),
                        replace(self.command, code=" "),
                        replace(self.command, name="\x00"),
                        replace(self.command, expected_version=-1)):
            with self.subTest(command=command):
                with self.assertRaises(ProjectDepartmentPatchError) as caught:
                    self.service.patch(command)
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_non_manager_cross_project_archived_denied(self):
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectDepartmentPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.role = "PROJECT_MANAGER"
        self.auth_facts.owner = uuid.uuid4()
        with self.assertRaises(ProjectDepartmentPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.owner = self.project_id
        self.auth_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectDepartmentPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repo.calls, 0)

    def test_missing_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectDepartmentPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")


if __name__ == "__main__":
    unittest.main()
