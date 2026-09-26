from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import ProjectActorFacts, ProjectAuthorizationService
from plm_assistant.modules.project.application.change_member_state import (
    ChangeProjectMemberState, ProjectMemberStateError, ProjectMemberStateService,
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
        self.owner = project_id
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"

    def actor_facts(self, _tx, **_kwargs):
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, _tx, **_kwargs):
        return self.owner


class Repository:
    def __init__(self, facts):
        self.facts = facts
        self.previous_state = "ACTIVE"
        self.calls = 0
        self.saved = {}

    def change(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts, self.previous_state

    def save_state_result(self, _tx, *, result_id, project_id, operation, view, version):
        self.saved[(result_id, project_id, operation)] = view

    def get_state_result(self, _tx, *, result_id, project_id, member_id, operation):
        view = self.saved.get((result_id, project_id, operation))
        return view if view is not None and view.member_id == member_id else None


class Receipts:
    def __init__(self):
        self.values = {}

    def reserve(self, _tx, *, scope, request_fingerprint):
        from plm_assistant.modules.platform.application.idempotency import IdempotencyError
        key = (scope.actor_id, scope.project_id, scope.operation, scope.key_digest)
        value = self.values.get(key)
        if value is not None:
            if value[0] != request_fingerprint:
                raise IdempotencyError("CONFLICT_IDEMPOTENCY")
            return value[1]
        self.values[key] = (request_fingerprint, None)
        return None

    def complete(self, _tx, *, scope, result):
        key = (scope.actor_id, scope.project_id, scope.operation, scope.key_digest)
        self.values[key] = (self.values[key][0], result)


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["event"] = event


class ProjectMemberStateTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.project_id, self.member_id, department_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.access, self.guard = Access(), Guard()
        self.auth_facts = AuthorizationFacts(self.project_id)
        self.repository = Repository(MemberFacts(
            self.member_id, self.project_id, uuid.uuid4(), "CUSTOMER_MEMBER",
            department_id, "部门", "SUSPENDED", datetime.now(timezone.utc), None, 1,
        ))
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.auth_facts,
        )
        self.service = ProjectMemberStateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repository, audit=Audit(self.state),
        )
        self.command = ChangeProjectMemberState(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id, self.member_id, 0,
        )
        self.service._receipts = Receipts()

    def test_each_operation_uses_its_policy_and_audit(self):
        cases = (("suspend", "SUSPEND", "SUSPENDED"),
                 ("resume", "RESUME", "RESUMED"),
                 ("remove", "REMOVE", "REMOVED"))
        for method, op, action in cases:
            with self.subTest(method=method):
                self.state.pop("event", None)
                view = getattr(self.service, method)(self.command)
                self.assertEqual(view.etag, '"v1"')
                self.assertEqual(self.repository.kwargs["operation"], op)
                self.assertEqual(self.state["event"].action, "PROJECT_MEMBER_" + action)
                self.assertEqual(self.state["event"].before_state, "ACTIVE")
        self.assertEqual(self.state["commits"], 3)

    def test_validation_before_license(self):
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.suspend(replace(self.command, expected_version=-1))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(self.guard.calls, 0)

    def test_cross_project_and_archived_denied(self):
        self.auth_facts.owner = uuid.uuid4()
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.remove(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.owner = self.project_id
        self.auth_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.remove(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repository.calls, 0)

    def test_non_manager_denied(self):
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.remove(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repository.calls, 0)

    def test_missing_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.resume(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")

    def test_invalid_repository_projection_rolls_back(self):
        self.repository.facts = None
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.remove(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.assertEqual(self.state["commits"], 0)

    def test_idempotent_state_replays_first_view_and_conflicts_on_version(self):
        first = self.service.suspend_idempotent(
            self.command, idempotency_key="member-state-key-001",
        )
        self.access.name = "Renamed User"
        second = self.service.suspend_idempotent(
            self.command, idempotency_key="member-state-key-001",
        )
        self.assertEqual(first, second)
        self.assertEqual(second.user_display_name, "Synthetic User")
        self.assertEqual(self.repository.calls, 1)
        self.assertEqual(self.state["commits"], 1)
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.suspend_idempotent(
                replace(self.command, expected_version=1),
                idempotency_key="member-state-key-001",
            )
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")

    def test_idempotent_replay_rechecks_role_and_target_ownership(self):
        self.service.suspend_idempotent(
            self.command, idempotency_key="member-state-key-002",
        )
        self.auth_facts.owner = uuid.uuid4()
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.suspend_idempotent(
                self.command, idempotency_key="member-state-key-002",
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.auth_facts.owner = self.project_id
        self.auth_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectMemberStateError) as caught:
            self.service.suspend_idempotent(
                self.command, idempotency_key="member-state-key-002",
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
