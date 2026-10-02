from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, RevokedTraceLink, TraceLinkState,
    TraceRevokeError, TraceRevokeService,
)


class _Tx:
    committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.committed = True


class _Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class _Session:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, tx, *, session_token, csrf_token, now):
        if csrf_token != b"c" * 32:
            return None
        return self.actor


class _Projects:
    def __init__(self, role):
        self.role = role

    def require_in_transaction(self, tx, *, user_id, project_id, operation):
        assert operation == "TRACE_LINK_REVOKE"
        return AuthorizedProjectAction(user_id, project_id, operation, self.role)


class _Repository:
    def __init__(self, state):
        self.state = state
        self.writes = 0

    def lock(self, tx, *, project_id, trace_link_id):
        if self.state.project_id != project_id or self.state.trace_link_id != trace_link_id:
            return None
        return self.state

    def revoke(self, tx, *, project_id, trace_link_id, expected_version):
        assert self.state.link_state == "ACTIVE"
        assert self.state.lock_version == expected_version
        self.writes += 1
        self.state = replace(self.state, link_state="REVOKED", lock_version=1)
        return 1


class _Receipts:
    def __init__(self):
        self.completed = {}
        self.completions = 0

    def reserve(self, tx, *, scope, request_fingerprint):
        self.pending_key = scope.key_digest
        self.pending_fingerprint = request_fingerprint
        stored = self.completed.get(scope.key_digest)
        if stored is not None and stored[0] != request_fingerprint:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return None if stored is None else stored[1]

    def complete(self, tx, *, scope, result):
        self.completed[scope.key_digest] = (self.pending_fingerprint, result)
        self.completions += 1


class _Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)


class TraceRevokeUnitTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.link = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.command = RevokeTraceLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.link, 0,
        )
        self.tx = _Tx()
        self.guard, self.session = _Guard(), _Session(self.actor)
        self.projects = _Projects("PROJECT_MANAGER")
        self.repo = _Repository(TraceLinkState(self.link, self.project, "ACTIVE", 0))
        self.receipts, self.audit = _Receipts(), _Audit()
        self.service = TraceRevokeService(
            unit_of_work=lambda: self.tx, sessions=self.session,
            projects=self.projects, license_guard=self.guard,
            repository=self.repo, receipts=self.receipts, audit=self.audit,
            clock=lambda: datetime.now(timezone.utc),
        )

    def test_first_write_and_same_key_replay_have_one_audit(self):
        first = self.service.revoke(self.command, idempotency_key="trace-revoke-key-001")
        self.assertEqual(first, RevokedTraceLink(self.link, 1))
        self.assertTrue(self.tx.committed)
        self.assertEqual((self.repo.writes, self.receipts.completions,
                          len(self.audit.events)), (1, 1, 1))
        self.assertEqual(
            self.service.revoke(self.command, idempotency_key="trace-revoke-key-001"),
            first,
        )
        self.assertEqual((self.repo.writes, self.receipts.completions,
                          len(self.audit.events)), (1, 1, 1))

    def test_current_license_session_role_and_scope_fail_closed(self):
        for mutate, code in (
            (lambda: setattr(self.guard, "enabled", False), "LICENSE_OPERATION_DENIED"),
            (lambda: setattr(self.session, "actor", None), "AUTH_ACCESS_DENIED"),
            (lambda: setattr(self.projects, "role", "IMPLEMENTATION_MEMBER"), "RESOURCE_NOT_FOUND"),
            (lambda: setattr(self.repo, "state", replace(self.repo.state,
                                                         project_id=uuid.uuid4())),
             "RESOURCE_NOT_FOUND"),
        ):
            self.setUp()
            mutate()
            with self.subTest(code=code), self.assertRaises(TraceRevokeError) as caught:
                self.service.revoke(self.command, idempotency_key="trace-revoke-key-001")
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.repo.writes, 0)

    def test_version_terminal_key_conflict_and_validation(self):
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(replace(self.command, expected_version=1),
                                idempotency_key="trace-revoke-key-001")
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        self.service.revoke(self.command, idempotency_key="trace-revoke-key-001")
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(self.command, idempotency_key="trace-revoke-key-002")
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(replace(self.command, expected_version=1),
                                idempotency_key="trace-revoke-key-002")
        self.assertEqual(caught.exception.code, "CONFLICT_STATE")
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(replace(self.command, expected_version=1),
                                idempotency_key="trace-revoke-key-001")
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(replace(self.command, session_token=b"short"),
                                idempotency_key="trace-revoke-key-003")
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_audit_failure_prevents_commit(self):
        self.audit.fail = True
        with self.assertRaises(TraceRevokeError) as caught:
            self.service.revoke(self.command, idempotency_key="trace-revoke-key-001")
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")
        self.assertFalse(self.tx.committed)


if __name__ == "__main__":
    unittest.main()
