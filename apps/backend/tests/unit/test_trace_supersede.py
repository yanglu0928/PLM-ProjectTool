from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.trace.application.create_link import StoredTraceLink
from plm_assistant.modules.trace.application.supersede_link import (
    SupersedeTraceLink, SupersededTraceLink, TraceSupersedeError,
    TraceSupersedeService, TraceSupersedeState,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProof
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.cycle_guard import TraceCycleError


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


class _Sessions:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, tx, *, session_token, csrf_token, now):
        return self.actor if csrf_token == b"c" * 32 else None


class _Projects:
    role = "PROJECT_MANAGER"

    def require_in_transaction(self, tx, *, user_id, project_id, operation):
        assert operation == "TRACE_LINK_SUPERSEDE"
        return AuthorizedProjectAction(user_id, project_id, operation, self.role)


class _Owner:
    def prove(self, tx, query, ref):
        return TraceTargetProof(ref)


class _Cycles:
    reject = False

    def assert_acyclic(self, tx, edge):
        if self.reject:
            raise TraceCycleError()


class _Repository:
    def __init__(self, state):
        self.state = state
        self.new_id = uuid.uuid4()
        self.inserted = True
        self.created = self.changed = 0

    def lock(self, tx, *, project_id, trace_link_id):
        return self.state if (self.state.project_id == project_id
                              and self.state.trace_link_id == trace_link_id) else None

    def create_active(self, tx, *, edge, actor_id, trace_id):
        self.created += 1
        return StoredTraceLink(self.new_id, self.inserted)

    def supersede(self, tx, *, project_id, trace_link_id, expected_version,
                  replacement_id):
        self.changed += 1
        self.state = replace(self.state, link_state="SUPERSEDED", lock_version=1,
                             superseded_by_ref=replacement_id)
        return 1


class _Receipts:
    def __init__(self):
        self.saved = {}
        self.completions = 0

    def reserve(self, tx, *, scope, request_fingerprint):
        record = self.saved.get(scope.key_digest)
        if record is not None and record[0] != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        self.scope, self.fingerprint = scope, request_fingerprint
        return None if record is None else record[1]

    def complete(self, tx, *, scope, result):
        self.saved[scope.key_digest] = (self.fingerprint, result)
        self.completions += 1


class _Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("audit failed")
        self.events.append(event)


class TraceSupersedeTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.link = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        source = TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                 "PROJECT", self.project)
        target = TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                 "PROJECT", self.project)
        other = TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                "PROJECT", self.project)
        self.old = TraceEdgeShape(source, target, "DERIVED_FROM")
        self.new = TraceEdgeShape(source, other, "DERIVED_FROM")
        self.command = SupersedeTraceLink(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.link, 0, self.new,
        )
        self.tx = _Tx()
        self.guard, self.sessions = _Guard(), _Sessions(self.actor)
        self.projects = _Projects()
        self.repository = _Repository(TraceSupersedeState(
            self.link, self.project, "ACTIVE", 0, self.old, None,
        ))
        self.receipts, self.audit, self.cycles = _Receipts(), _Audit(), _Cycles()
        from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService
        self.service = TraceSupersedeService(
            unit_of_work=lambda: self.tx, sessions=self.sessions,
            projects=self.projects, license_guard=self.guard,
            proofs=TraceTargetProofService({("document", "DOC-02"): _Owner()}),
            cycle_guard=self.cycles, repository=self.repository,
            receipts=self.receipts, audit=self.audit,
            clock=lambda: datetime.now(timezone.utc),
        )

    def _attempt(self, command=None, key="trace-supersede-key-001"):
        return self.service.supersede(command or self.command, idempotency_key=key)

    def test_new_edge_and_same_key_replay(self):
        first = self._attempt()
        self.assertEqual(first, SupersededTraceLink(self.link,
                                                     self.repository.new_id, 1))
        self.assertTrue(self.tx.committed)
        self.assertEqual((self.repository.created, self.repository.changed,
                          self.receipts.completions, len(self.audit.events)),
                         (1, 1, 1, 2))
        self.assertEqual(self._attempt(), first)
        self.assertEqual((self.repository.created, self.repository.changed,
                          self.receipts.completions, len(self.audit.events)),
                         (1, 1, 1, 2))

    def test_authorization_and_validation_fail_closed(self):
        cases = (
            (lambda: setattr(self.guard, "enabled", False), "LICENSE_OPERATION_DENIED"),
            (lambda: setattr(self.sessions, "actor", None), "AUTH_ACCESS_DENIED"),
            (lambda: setattr(self.projects, "role", "IMPLEMENTATION_MEMBER"),
             "RESOURCE_NOT_FOUND"),
            (lambda: setattr(self.repository, "state", replace(
                self.repository.state, project_id=uuid.uuid4())), "RESOURCE_NOT_FOUND"),
        )
        for mutate, code in cases:
            self.setUp()
            mutate()
            with self.subTest(code=code), self.assertRaises(TraceSupersedeError) as caught:
                self._attempt()
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(self.repository.created, 0)
        self.setUp()
        for bad in (
            replace(self.command, session_token=b"short"),
            replace(self.command, replacement=self.old),
            replace(self.command, replacement=TraceEdgeShape(
                TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                "PROJECT", self.project),
                TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                "PROJECT", self.project), "DERIVED_FROM")),
        ):
            with self.assertRaises(TraceSupersedeError) as caught:
                self._attempt(bad)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_versions_existing_edge_cycle_and_audit_failure(self):
        with self.assertRaises(TraceSupersedeError) as caught:
            self._attempt(replace(self.command, expected_version=1))
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        self.repository.inserted = False
        with self.assertRaises(TraceSupersedeError) as caught:
            self._attempt()
        self.assertEqual(caught.exception.code, "CONFLICT_STATE")
        self.assertEqual(self.repository.changed, 0)
        self.setUp()
        self.cycles.reject = True
        with self.assertRaises(TraceSupersedeError) as caught:
            self._attempt()
        self.assertEqual(caught.exception.code, "CONFLICT_STATE")
        self.setUp()
        self.audit.fail = True
        with self.assertRaises(TraceSupersedeError) as caught:
            self._attempt()
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")
        self.assertFalse(self.tx.committed)


if __name__ == "__main__":
    unittest.main()
