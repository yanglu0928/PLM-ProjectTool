from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.application.create_project import (
    CreateProject, CreatedProject, DepartmentSeed, ProjectCreateError, ProjectCreateService,
)


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
    def __init__(self, state):
        self.state = state
        self.actor = uuid.uuid4()
        self.eligible = True

    def authorized_admin(self, *_args, **_kwargs):
        self.state["checks"] += 1
        return self.actor

    def lock_eligible_manager(self, *_args):
        return self.eligible


class Guard:
    def __init__(self, state):
        self.state = state

    def require_valid(self, *, trace_id):
        self.state["guard"] += 1


class Repo:
    def __init__(self, state):
        self.state = state
        self.result = CreatedProject(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "P1", "项目一")

    def create(self, *_args, **kwargs):
        self.state["kwargs"] = kwargs
        return self.result

    def created_at(self, *_args):
        return datetime(2026, 9, 25, tzinfo=timezone.utc)


class Receipts:
    def __init__(self):
        self.saved = None

    def reserve(self, _tx, *, scope, request_fingerprint):
        if self.saved is None:
            self.fingerprint = request_fingerprint
            return None
        if self.fingerprint != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return self.saved

    def complete(self, _tx, *, scope, result):
        self.saved = result


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["audit"] = event


class ProjectCreateTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(commits=0, checks=0, guard=0)
        self.access = Access(self.state)
        self.repo = Repo(self.state)
        self.service = ProjectCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=Guard(self.state), repository=self.repo,
            audit=Audit(self.state),
        )
        self.command = CreateProject(b"s" * 32, b"c" * 32, uuid.uuid4(), " Ｐ１ ",
                                     " 项目一 ", uuid.uuid4())

    def test_atomic_default_department_and_audit(self):
        result = self.service.create(self.command)
        self.assertEqual(result, self.repo.result)
        self.assertEqual(self.state["checks"], 2)
        self.assertEqual(self.state["guard"], 1)
        self.assertEqual(self.state["commits"], 1)
        self.assertEqual(self.state["kwargs"]["normalized_code"], "p1")
        self.assertEqual(self.state["kwargs"]["department_code"], "DEFAULT")
        self.assertEqual(self.state["audit"].target_project_id, result.project_id)

    def test_explicit_department_seed(self):
        cmd = CreateProject(b"s" * 32, b"c" * 32, uuid.uuid4(), "A", "项目", uuid.uuid4(),
                            DepartmentSeed(" R&D ", " 研发 "))
        self.service.create(cmd)
        self.assertEqual(self.state["kwargs"]["department_normalized_code"], "r&d")
        self.assertEqual(self.state["kwargs"]["department_name"], "研发")

    def test_invalid_input_rejected_before_guard(self):
        for code in ("", "\x00", "x" * 65):
            cmd = CreateProject(b"s" * 32, b"c" * 32, uuid.uuid4(), code, "项目", uuid.uuid4())
            with self.subTest(code=code), self.assertRaises(ProjectCreateError):
                self.service.create(cmd)
        self.assertEqual(self.state["guard"], 0)
        self.assertEqual(self.state["commits"], 0)

    def test_ineligible_manager_denied_before_write(self):
        self.access.eligible = False
        with self.assertRaises(ProjectCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_MANAGER_INVALID")
        self.assertNotIn("kwargs", self.state)
        self.assertEqual(self.state["commits"], 0)

    def test_duplicate_code_rolls_back_without_audit(self):
        self.repo.result = None
        with self.assertRaises(ProjectCreateError) as caught:
            self.service.create(self.command)
        self.assertEqual(caught.exception.code, "PROJECT_CODE_CONFLICT")
        self.assertNotIn("audit", self.state)
        self.assertEqual(self.state["commits"], 0)

    def test_idempotent_create_replays_original_view_without_repeat_write(self):
        receipts = Receipts()
        service = ProjectCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=Guard(self.state), repository=self.repo,
            audit=Audit(self.state), receipts=receipts,
        )
        first = service.create_idempotent(self.command, idempotency_key="a" * 16)
        self.state.pop("kwargs")
        replay = service.create_idempotent(self.command, idempotency_key="a" * 16)
        self.assertEqual(first, replay)
        self.assertEqual(first.etag, '"v0"')
        self.assertEqual(first.project_id, self.repo.result.project_id)
        self.assertNotIn("kwargs", self.state)
        self.assertEqual(self.state["commits"], 1)

    def test_idempotent_create_rejects_changed_payload(self):
        receipts = Receipts()
        service = ProjectCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=Guard(self.state), repository=self.repo,
            audit=Audit(self.state), receipts=receipts,
        )
        service.create_idempotent(self.command, idempotency_key="a" * 16)
        changed = CreateProject(
            self.command.session_token, self.command.csrf_token,
            uuid.uuid4(), "P2", self.command.name,
            self.command.initial_manager_user_id,
        )
        with self.assertRaises(ProjectCreateError) as caught:
            service.create_idempotent(changed, idempotency_key="a" * 16)
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")
        self.assertEqual(self.state["commits"], 1)

    def test_workflow_bootstrap_uses_authorized_actor_and_same_transaction_once(self):
        calls = []
        class Initializer:
            def initialize_in_transaction(inner, tx, **kwargs):
                calls.append((tx, kwargs))
                return uuid.uuid4()
        service = ProjectCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=Guard(self.state), repository=self.repo, audit=Audit(self.state),
            receipts=Receipts(), workflow_initializer=Initializer(),
        )
        first = service.create_idempotent(self.command, idempotency_key="w"*16)
        self.assertEqual(service.create_idempotent(self.command, idempotency_key="w"*16), first)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0].state, self.state)
        self.assertEqual(calls[0][1], dict(
            project_id=first.project_id, actor_id=self.access.actor, trace_id=self.command.trace_id,
        ))

    def test_workflow_failure_prevents_project_audit_and_commit(self):
        class Initializer:
            def initialize_in_transaction(inner, tx, **kwargs):
                raise RuntimeError("synthetic initializer failure")
        service = ProjectCreateService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=Guard(self.state), repository=self.repo, audit=Audit(self.state),
            workflow_initializer=Initializer(),
        )
        with self.assertRaises(RuntimeError):
            service.create(self.command)
        self.assertNotIn("audit", self.state)
        self.assertEqual(self.state["commits"], 0)


if __name__ == "__main__":
    unittest.main()
