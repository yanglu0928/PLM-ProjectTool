from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.trace.application.create_link import (
    CreateTraceLink, CreateTraceLinkRefs, StoredTraceLink,
    TraceCreateError, TraceCreateService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TracePublicEdgeResolver, TraceResourceVersionRef,
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
    enabled = True
    refs = ()

    def prove(self, transaction, query, ref):
        if not self.enabled:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self.calls += 1
        return TraceTargetProof(ref)

    def resolve(self, transaction, query, project_id, ref):
        if not self.enabled:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        for actual in self.refs:
            if (actual.object_type == ref.resource_type
                    and actual.object_id == ref.resource_id
                    and actual.version_id == ref.version_id
                    and actual.project_id == project_id):
                return actual
        raise TraceTargetProofError("RESOURCE_NOT_FOUND")


class _Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class _Receipts:
    def __init__(self):
        self.result = None
        self.fingerprint = None

    def reserve(self, transaction, *, scope, request_fingerprint):
        if self.fingerprint is not None and self.fingerprint != request_fingerprint:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
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
        self.belongs = True

    def exists_in_project(self, transaction, *, project_id, trace_link_id):
        return self.belongs and trace_link_id == self.link_id

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
        self.owner.refs = (source, target)
        self.guard = _Guard()
        self.cycles, self.repository, self.audit = _Cycles(), _Repository(), _Audit()
        self.service = TraceCreateService(
            unit_of_work=self._uow, sessions=self.session,
            projects=ProjectAuthorizationService(
                unit_of_work=self._uow, repository=self.facts,
            ),
            license_guard=self.guard,
            proofs=TraceTargetProofService({("document", "DOC-02"): self.owner}),
            cycle_guard=self.cycles, repository=self.repository,
            receipts=self.receipts, audit=self.audit,
            public_resolver=TracePublicEdgeResolver({"DOC-02": self.owner}),
            clock=lambda: datetime.now(timezone.utc),
        )

    def _uow(self):
        tx = _Uow()
        self.uows.append(tx)
        return tx

    def test_create_and_same_key_replay_only_one_audit(self):
        first = self.service.create(self.command, idempotency_key="same-key-12345678")
        self.owner.enabled = False
        second = self.service.create(self.command, idempotency_key="same-key-12345678")
        self.assertEqual(first, second)
        self.assertEqual(first.trace_link_id, self.repository.link_id)
        self.assertEqual(self.repository.calls, 1)
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(self.audit.events[0].action, "TRACE_LINK_CREATED")
        self.assertTrue(self.uows[0].committed)
        self.assertFalse(self.uows[1].committed)

    def test_public_refs_replay_after_source_restricted_and_current_guard(self):
        edge = self.command.edge
        command = CreateTraceLinkRefs(
            self.command.session_token, self.command.csrf_token,
            self.command.trace_id, self.project_id,
            TraceResourceVersionRef(edge.source.object_type, edge.source.object_id,
                                    edge.source.version_id),
            TraceResourceVersionRef(edge.target.object_type, edge.target.object_id,
                                    edge.target.version_id),
            edge.relation_type,
        )
        first = self.service.create_refs(
            command, idempotency_key="trace-create-public-001",
        )
        self.owner.enabled = False
        self.assertEqual(self.service.create_refs(
            command, idempotency_key="trace-create-public-001",
        ), first)
        self.assertEqual((self.repository.calls, len(self.audit.events)), (1, 1))
        with self.assertRaises(TraceCreateError) as caught:
            self.service.create_refs(
                replace(command, relation_type="IMPLEMENTS"),
                idempotency_key="trace-create-public-001",
            )
        self.assertEqual(caught.exception.code, "CONFLICT_IDEMPOTENCY")
        self.guard.enabled = False
        with self.assertRaises(TraceCreateError) as caught:
            self.service.create_refs(command, idempotency_key="trace-create-public-001")
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.guard.enabled = True
        self.repository.belongs = False
        with self.assertRaises(TraceCreateError) as caught:
            self.service.create_refs(command, idempotency_key="trace-create-public-001")
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")

    def test_public_refs_unknown_owner_and_invalid_input_rejected(self):
        edge = self.command.edge
        command = CreateTraceLinkRefs(
            self.command.session_token, self.command.csrf_token,
            self.command.trace_id, self.project_id,
            TraceResourceVersionRef(edge.source.object_type, edge.source.object_id,
                                    edge.source.version_id),
            TraceResourceVersionRef("REQ-03", uuid.uuid4(), uuid.uuid4()),
            edge.relation_type,
        )
        with self.assertRaises(TraceTargetProofError) as caught:
            self.service.create_refs(
                command, idempotency_key="trace-create-public-002",
            )
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(self.repository.calls, 0)
        with self.assertRaises(TraceCreateError) as caught:
            self.service.create_refs(
                replace(command, project_id=uuid.UUID(int=0)),
                idempotency_key="trace-create-public-002",
            )
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

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
        self.assertIsNone(self.receipts.result)


if __name__ == "__main__":
    unittest.main()
