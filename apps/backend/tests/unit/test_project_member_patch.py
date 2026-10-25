from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.patch_member import (
    PatchProjectMember, ProjectMemberPatchError, ProjectMemberPatchService,
)
from plm_assistant.modules.project.application.read_members import MemberFacts


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
        self.name = "Synthetic User"

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor

    def display_name(self, *_args):
        return self.name


class Guard:
    def __init__(self):
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1


class AuthorizationFacts:
    def __init__(self, project_id):
        self.project_id = project_id
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.owner = project_id

    def actor_facts(self, _tx, **kwargs):
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, _tx, **kwargs):
        return self.owner


class Repository:
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


class ProjectMemberPatchTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.project_id, self.member_id, self.department_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.access, self.guard = Access(), Guard()
        self.auth_facts = AuthorizationFacts(self.project_id)
        self.repository = Repository(MemberFacts(
            self.member_id, self.project_id, uuid.uuid4(), "CUSTOMER_MEMBER",
            self.department_id, "部门", "ACTIVE", datetime.now(timezone.utc), None, 1,
        ))
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.auth_facts,
        )
        self.service = ProjectMemberPatchService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repository, audit=Audit(self.state),
        )
        self.command = PatchProjectMember(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            self.member_id, 0, role="CUSTOMER_MEMBER",
        )

    def test_changed_patch_audited_and_versioned(self):
        view = self.service.patch(self.command)
        self.assertEqual(view.etag, '"v1"')
        self.assertEqual(view.role, "CUSTOMER_MEMBER")
        self.assertEqual(self.repository.kwargs["expected_version"], 0)
        self.assertEqual(self.state["event"].action, "PROJECT_MEMBER_PATCHED")
        self.assertEqual(self.state["commits"], 1)

    def test_noop_does_not_emit_false_history_audit(self):
        self.repository.changed = False
        self.service.patch(self.command)
        self.assertNotIn("event", self.state)

    def test_invalid_input_before_license(self):
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(replace(self.command, role=None))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(replace(self.command, role="OWNER"))
        self.assertEqual(caught.exception.code, "PROJECT_ROLE_INVALID")
        self.assertEqual(self.guard.calls, 0)

    def test_cross_project_and_archived_denied(self):
        self.auth_facts.owner = uuid.uuid4()
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.owner = self.project_id
        self.auth_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repository.calls, 0)

    def test_no_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repository.calls, 0)

    def test_bad_projection_rolls_back(self):
        self.repository.facts = None
        with self.assertRaises(ProjectMemberPatchError) as caught:
            self.service.patch(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.assertEqual(self.state["commits"], 0)


if __name__ == "__main__":
    unittest.main()
