"""Internal PROJECT TraceLink create; public HTTP wiring is separate."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TracePublicEdgeResolver, TraceResourceVersionRef,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


_OPERATION = "V1_TRACE_LINK_CREATE"
_RESULT_TYPE = "V1_TRACE_LINK"


class TraceCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateTraceLink:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    edge: TraceEdgeShape


@dataclass(frozen=True, slots=True)
class CreateTraceLinkRefs:
    """Frozen three-field inputs, resolved only within the create transaction."""

    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    source: TraceResourceVersionRef
    target: TraceResourceVersionRef
    relation_type: str


@dataclass(frozen=True, slots=True)
class CreatedTraceLink:
    trace_link_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class StoredTraceLink:
    trace_link_id: uuid.UUID
    inserted: bool


class TraceWriteSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class TraceProjectAuthorizationPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str,
                               resource_id: uuid.UUID | None = None) -> AuthorizedProjectAction: ...


class TraceCyclePort(Protocol):
    def assert_acyclic(self, transaction: object, edge: TraceEdgeShape) -> None: ...


class TraceCreateLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class TraceCreateRepositoryPort(Protocol):
    def exists_in_project(self, transaction: object, *, project_id: uuid.UUID,
                          trace_link_id: uuid.UUID) -> bool: ...
    def create_active(self, transaction: object, *, edge: TraceEdgeShape,
                      actor_id: uuid.UUID, trace_id: uuid.UUID) -> StoredTraceLink: ...


class TraceCreateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def _ref_fingerprint(ref: TraceVersionRef) -> dict[str, str | None]:
    return {
        "owner_module": ref.owner_module,
        "object_type": ref.object_type,
        "object_id": str(ref.object_id),
        "version_id": str(ref.version_id),
        "scope": ref.scope,
        "project_id": str(ref.project_id) if ref.project_id is not None else None,
    }


class TraceCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 sessions: TraceWriteSessionPort,
                 projects: TraceProjectAuthorizationPort,
                 license_guard: TraceCreateLicensePort,
                 proofs: TraceTargetProofService,
                 cycle_guard: TraceCyclePort,
                 repository: TraceCreateRepositoryPort,
                 receipts: TraceCreateReceiptPort,
                 audit: AuditService,
                 public_resolver: TracePublicEdgeResolver | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, sessions, projects, license_guard, proofs, cycle_guard,
                repository, receipts, audit)):
            raise ValueError("Trace create dependencies are required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._public_resolver = license_guard, public_resolver
        self._proofs, self._cycles, self._repository = proofs, cycle_guard, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateTraceLink, *, idempotency_key: str) -> CreatedTraceLink:
        return self._execute(command, idempotency_key=idempotency_key)

    def create_refs(self, command: CreateTraceLinkRefs, *,
                    idempotency_key: str) -> CreatedTraceLink:
        return self._execute(command, idempotency_key=idempotency_key)

    def _execute(self, command: CreateTraceLink | CreateTraceLinkRefs, *,
                 idempotency_key: str) -> CreatedTraceLink:
        if (type(command) not in (CreateTraceLink, CreateTraceLinkRefs)
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise TraceCreateError("VALIDATION_FAILED")
        public = type(command) is CreateTraceLinkRefs
        if public:
            if (type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                    or type(command.source) is not TraceResourceVersionRef
                    or type(command.target) is not TraceResourceVersionRef
                    or type(command.relation_type) is not str or not command.relation_type
                    or any(type(ref.resource_type) is not str or not ref.resource_type
                           or type(ref.resource_id) is not uuid.UUID
                           or ref.resource_id.int == 0
                           or type(ref.version_id) is not uuid.UUID
                           or ref.version_id.int == 0
                           for ref in (command.source, command.target))
                    or self._public_resolver is None):
                raise TraceCreateError("VALIDATION_FAILED")
            project_id = command.project_id
            fingerprint_input = {
                "source": {"resource_type": command.source.resource_type,
                           "resource_id": str(command.source.resource_id),
                           "version_id": str(command.source.version_id)},
                "target": {"resource_type": command.target.resource_type,
                           "resource_id": str(command.target.resource_id),
                           "version_id": str(command.target.version_id)},
                "relation_type": command.relation_type,
            }
        else:
            if (type(command.edge) is not TraceEdgeShape
                    or command.edge.scope != "PROJECT"
                    or type(command.edge.project_id) is not uuid.UUID):
                raise TraceCreateError("VALIDATION_FAILED")
            project_id = command.edge.project_id
            fingerprint_input = {
                "source": _ref_fingerprint(command.edge.source),
                "target": _ref_fingerprint(command.edge.target),
                "relation_type": command.edge.relation_type,
            }
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint(fingerprint_input)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise TraceCreateError("TRACE_UNAVAILABLE")
                actor = self._sessions.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise TraceCreateError("AUTH_ACCESS_DENIED")
                self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=project_id,
                    operation="TRACE_LINK_CREATE",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != _RESULT_TYPE or replay.status_code != 201
                            or self._repository.exists_in_project(
                                tx, project_id=project_id,
                                trace_link_id=replay.ref_id) is not True):
                        raise TraceCreateError("TRACE_UNAVAILABLE")
                    return CreatedTraceLink(replay.ref_id)
                edge = (self._public_resolver.resolve_edge(
                    tx, TraceProofQuery(command.session_token, command.trace_id),
                    project_id, command.source, command.target, command.relation_type,
                ) if public else command.edge)
                self._proofs.prove_edge(
                    tx, TraceProofQuery(command.session_token, command.trace_id), edge,
                )
                self._cycles.assert_acyclic(tx, edge)
                stored = self._repository.create_active(
                    tx, edge=edge, actor_id=actor, trace_id=command.trace_id,
                )
                if (type(stored) is not StoredTraceLink
                        or type(stored.trace_link_id) is not uuid.UUID
                        or stored.trace_link_id.int == 0
                        or type(stored.inserted) is not bool):
                    raise TraceCreateError("TRACE_UNAVAILABLE")
                if stored.inserted:
                    self._audit.append(tx, AuditEventDraft(
                        trace_id=command.trace_id, event_scope="PROJECT",
                        target_project_id=project_id,
                        actor_type="USER", actor_id=actor,
                        original_actor_id=None, actor_hint_digest=None,
                        action="TRACE_LINK_CREATED", outcome="SUCCESS",
                        target_owner_module="trace", target_object_type="TRC-01",
                        target_object_id=stored.trace_link_id, after_state="ACTIVE",
                    ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_RESULT_TYPE, stored.trace_link_id, 201),
                )
                tx.commit()
                return CreatedTraceLink(stored.trace_link_id)
        except IdempotencyError as exc:
            raise TraceCreateError(exc.code) from None
        except ProjectAuthorizationError as exc:
            raise TraceCreateError(exc.code) from None
        except RuntimeLicenseError:
            raise TraceCreateError("LICENSE_OPERATION_DENIED") from None
