from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.create_member import (
    CreateProjectMember, ProjectMemberCreateError, ProjectMemberCreateService,
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

    def lock_eligible_member(self, *_args):
        return self.name


class Guard:
    def __init__(self):
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1


class AuthorizationFacts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.state = "ACTIVE"
        self.lock = None

    def actor_facts(self, _tx, **kwargs):
        self.lock = kwargs["lock"]
        return None if self.role is None else ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("create has no target resource")


class Repo:
    def __init__(self):
        self.facts = None
        self.calls = 0
        self.saved = {}

    def create(self, _tx, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.facts

    def save_create_result(self, _tx, *, project_id, view):
        self.saved[(project_id, view.member_id)] = view

    def get_create_result(self, _tx, *, project_id, member_id):
        return self.saved.get((project_id, member_id))


class Receipts:
    def __init__(self):
        self.values = {}

    def reserve(self, _tx, *, scope, request_fingerprint):
        key = (scope.actor_id, scope.project_id, scope.operation, scope.key_digest)
        value = self.values.get(key)
        if value is not None:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
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


class ProjectMemberCreateTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.access, self.guard, self.authorization_facts, self.repo = (
            Access(), Guard(), AuthorizationFacts(), Repo(),
        )
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.authorization_facts,
        )
        self.service = ProjectMemberCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repo, audit=Audit(self.state),
        )
        self.project_id, self.user_id, self.department_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.command = CreateProjectMember(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            self.user_id, "IMPLEMENTATION_MEMBER", self.department_id,
        )
        self.repo.facts = MemberFacts(
            uuid.uuid4(), self.project_id, self.user_id, "IMPLEMENTATION_MEMBER",
            self.department_id, "研发部", "ACTIVE", datetime.now(timezone.utc), None, 0,
        )
        self.receipts = Receipts()
        self.service._receipts = self.receipts

    def test_creation_audited_and_scoped(self):
        view = self.service.create(self.command)
        self.assertEqual(view.user_display_name, "Synthetic User")
        self.assertEqual(view.etag, '"v0"')
        self.assertEqual(view.department_name, "研发部")
        self.assertTrue(self.authorization_facts.lock)
        self.assertEqual(self.state["event"].action, "PROJECT_MEMBER_CREATED")
        self.assertEqual(self.state["commits"], 1)

    def test_invalid_role_or_id_fails_before_license(self):
        invalid = CreateProjectMember(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project_id,
            self.user_id, "OWNER", self.department_id,
        )
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(invalid)
        self.assertEqual(caught.exception.code, "PROJECT_ROLE_INVALID")
        self.assertEqual(self.guard.calls, 0)
        self.assertEqual(self.repo.calls, 0)

    def test_non_manager_and_archived_denied(self):
        self.authorization_facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.authorization_facts.role = "PROJECT_MANAGER"
        self.authorization_facts.state = "ARCHIVED"
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertEqual(self.repo.calls, 0)

    def test_target_ineligible_denied(self):
        self.access.name = None
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_ROLE_INVALID")
        self.assertEqual(self.repo.calls, 0)

    def test_missing_session_denied(self):
        self.access.actor = None
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual(self.repo.calls, 0)

    def test_bad_repository_projection_does_not_audit(self):
        self.repo.facts = None
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_UNAVAILABLE")
        self.assertNotIn("event", self.state)
        self.assertEqual(self.state["commits"], 0)

    def test_idempotent_create_replays_original_view_not_mutated_names(self):
        first = self.service.create_idempotent(self.command, idempotency_key="member-create-key-001")
        self.access.name = "Renamed User"
        second = self.service.create_idempotent(self.command, idempotency_key="member-create-key-001")
        self.assertEqual(second, first)
        self.assertEqual(second.user_display_name, "Synthetic User")
        self.assertEqual(self.repo.calls, 1)
        self.assertEqual(self.state["commits"], 1)

    def test_idempotent_create_rejects_changed_payload(self):
        self.service.create_idempotent(self.command, idempotency_key="member-create-key-002")
        changed = CreateProjectMember(
            self.command.session_token, self.command.csrf_token, uuid.uuid4(),
            self.project_id, self.user_id, "CUSTOMER_MEMBER", self.department_id,
        )
        with self.assertRaises(ProjectMemberCreateError) as caught:
            self.service.create_idempotent(changed, idempotency_key="member-create-key-002")
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")
        self.assertEqual(self.repo.calls, 1)


if __name__ == "__main__":
    unittest.main()
