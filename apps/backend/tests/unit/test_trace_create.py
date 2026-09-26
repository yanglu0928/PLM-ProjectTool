from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.trace.application.create_link import (
    CreateTraceLink, StoredTraceLink, TraceCreateError, TraceCreateService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceTargetProof, TraceTargetProofError, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.cycle_guard import TraceCycleError


class _Uow:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.committed = True


class _Session:
    actor = uuid.uuid4()
    valid = True

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor if self.valid else None


class _Facts:
    role = "PROJECT_MANAGER"
    state = "ACTIVE"

    def actor_facts(self, *_args, **_kwargs):
        return ProjectActorFacts(self.state, self.role)


class _Owner:
    calls = 0

    def prove(self, transaction, query, ref):
        self.calls += 1
        return TraceTargetProof(ref)


class _Receipts:
    def __init__(self):
        self.result = None
        self.fingerprint = None

    def reserve(self, transaction, *, scope, request_fingerprint):
        if self.fingerprint is not None and self.fingerprint != request_fingerprint:
            raise RuntimeError("changed payload")
        self.fingerprint = request_fingerprint
        return self.result

    def complete(self, transaction, *, scope, result):
        self.result = result


class _Cycles:
    reject = False
    calls = 0

    def assert_acyclic(self, transaction, edge):
        self.calls += 1
        if self.reject:
            raise TraceCycleError()


class _Repository:
    def __init__(self):
        self.link_id = uuid.uuid4()
        self.inserted = True
        self.calls = 0

    def create_active(self, transaction, **_kwargs):
        self.calls += 1
        return StoredTraceLink(self.link_id, self.inserted)


class _Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, transaction, event):
        if self.fail:
            raise RuntimeError("audit failure")
        self.events.append(event)


class TraceCreateTests(unittest.TestCase):
    def setUp(self):
        self.project_id = uuid.uuid4()
        source = TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                 "PROJECT", self.project_id)
        target = TraceVersionRef("document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                                 "PROJECT", self.project_id)
        self.command = CreateTraceLink(b"s" * 32, b"c" * 32, uuid.uuid4(),
                                       TraceEdgeShape(source, target, "DERIVED_FROM"))
        self.uows = []
        self.session, self.facts = _Session(), _Facts()
        self.owner, self.receipts = _Owner(), _Receipts()
        self.cycles, self.repository, self.audit = _Cycles(), _Repository(), _Audit()
        self.service = TraceCreateService(
            unit_of_work=self._uow, sessions=self.session,
            projects=ProjectAuthorizationService(
                unit_of_work=self._uow, repository=self.facts,
            ),
            proofs=TraceTargetProofService({("document", "DOC-02"): self.owner}),
            cycle_guard=self.cycles, repository=self.repository,
            receipts=self.receipts, audit=self.audit,
            clock=lambda: datetime.now(timezone.utc),
        )

    def _uow(self):
        tx = _Uow()
        self.uows.append(tx)
        return tx

    def test_create_and_same_key_replay_only_one_audit(self):
        first = self.service.create(self.command, idempotency_key="same-key-12345678")
        second = self.service.create(self.command, idempotency_key="same-key-12345678")
        self.assertEqual(first, second)
        self.assertEqual(first.trace_link_id, self.repository.link_id)
        self.assertEqual(self.repository.calls, 1)
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(self.audit.events[0].action, "TRACE_LINK_CREATED")
        self.assertTrue(self.uows[0].committed)
        self.assertFalse(self.uows[1].committed)

    def test_existing_active_edge_has_no_second_audit(self):
        self.repository.inserted = False
        result = self.service.create(self.command, idempotency_key="another-key-1234")
        self.assertEqual(result.trace_link_id, self.repository.link_id)
        self.assertEqual(len(self.audit.events), 0)
        self.assertTrue(self.uows[0].committed)

    def test_permission_and_session_fail_before_receipt(self):
        for role in ("CUSTOMER_MANAGER", "CUSTOMER_MEMBER"):
            self.facts.role = role
            with self.subTest(role=role), self.assertRaises(TraceCreateError) as caught:
                self.service.create(self.command, idempotency_key="denied-key-123456")
            self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.facts.role = "IMPLEMENTATION_MEMBER"
        self.session.valid = False
        with self.assertRaises(TraceCreateError) as caught:
            self.service.create(self.command, idempotency_key="denied-key-123456")
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertIsNone(self.receipts.fingerprint)

    def test_cycle_and_audit_failure_do_not_commit(self):
        self.cycles.reject = True
        with self.assertRaises(TraceCycleError):
            self.service.create(self.command, idempotency_key="cycle-key-1234567")
        self.assertFalse(self.uows[-1].committed)
        self.cycles.reject = False
        self.audit.fail = True
        with self.assertRaises(RuntimeError):
            self.service.create(self.command, idempotency_key="audit-key-1234567")
        self.assertFalse(self.uows[-1].committed)

    def test_invalid_or_unregistered_target_denied(self):
        with self.assertRaises(TraceCreateError):
            self.service.create(replace(self.command, csrf_token=b"short"),
                                idempotency_key="invalid-key-12345")
        self.assertEqual(len(self.uows), 0)
        unknown = TraceVersionRef(
            "requirement", "REQ-03", uuid.uuid4(), uuid.uuid4(),
            "PROJECT", self.project_id,
        )
        edge = TraceEdgeShape(self.command.edge.source, unknown, "DERIVED_FROM")
        with self.assertRaises(TraceTargetProofError) as caught:
            self.service.create(replace(self.command, edge=edge),
                                idempotency_key="unknown-key-12345")
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertIsNone(self.receipts.fingerprint)


if __name__ == "__main__":
    unittest.main()
