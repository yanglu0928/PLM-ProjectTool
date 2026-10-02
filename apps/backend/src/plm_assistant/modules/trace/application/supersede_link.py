"""Internal atomic PROJECT TraceLink replacement by a current project manager."""

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
from plm_assistant.modules.trace.application.create_link import (
    StoredTraceLink, _ref_fingerprint,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TracePublicEdgeResolver, TraceResourceVersionRef,
    TraceTargetProofError, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape
from plm_assistant.modules.trace.infrastructure.cycle_guard import TraceCycleError


_OPERATION = "V1_TRACE_LINK_SUPERSEDE"
_RESULT_TYPE = "V1_TRACE_LINK_REPLACEMENT"


class TraceSupersedeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SupersedeTraceLink:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    trace_link_id: uuid.UUID
    expected_version: int
    replacement: TraceEdgeShape


@dataclass(frozen=True, slots=True)
class SupersedeTraceLinkRefs:
    """Frozen public three-field replacement, resolved only inside command UoW."""

    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    trace_link_id: uuid.UUID
    expected_version: int
    source: TraceResourceVersionRef
    target: TraceResourceVersionRef
    relation_type: str


@dataclass(frozen=True, slots=True)
class SupersededTraceLink:
    trace_link_id: uuid.UUID
    replacement_id: uuid.UUID
    lock_version: int


@dataclass(frozen=True, slots=True)
class TraceSupersedeState:
    trace_link_id: uuid.UUID
    project_id: uuid.UUID
    link_state: str
    lock_version: int
    edge: TraceEdgeShape
    superseded_by_ref: uuid.UUID | None


class _SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class _ProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class _LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class _CyclePort(Protocol):
    def assert_acyclic(self, transaction: object, edge: TraceEdgeShape) -> None: ...


class _RepositoryPort(Protocol):
    def lock(self, transaction: object, *, project_id: uuid.UUID,
             trace_link_id: uuid.UUID) -> TraceSupersedeState | None: ...
    def create_active(self, transaction: object, *, edge: TraceEdgeShape,
                      actor_id: uuid.UUID, trace_id: uuid.UUID) -> StoredTraceLink: ...
    def supersede(self, transaction: object, *, project_id: uuid.UUID,
                  trace_link_id: uuid.UUID, expected_version: int,
                  replacement_id: uuid.UUID) -> int: ...


class _ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class TraceSupersedeService:
    def __init__(self, *, unit_of_work: Callable[[], object], sessions: _SessionPort,
                 projects: _ProjectPort, license_guard: _LicensePort,
                 proofs: TraceTargetProofService, cycle_guard: _CyclePort,
                 repository: _RepositoryPort, receipts: _ReceiptPort,
                 audit: AuditService,
                 public_resolver: TracePublicEdgeResolver | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, sessions, projects, license_guard, proofs,
                cycle_guard, repository, receipts, audit)):
            raise ValueError("Trace supersede dependencies are required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._proofs, self._cycles = license_guard, proofs, cycle_guard
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._public_resolver = public_resolver
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def supersede(self, command: SupersedeTraceLink, *,
                  idempotency_key: str) -> SupersededTraceLink:
        return self._execute(command, idempotency_key=idempotency_key)

    def supersede_refs(self, command: SupersedeTraceLinkRefs, *,
                       idempotency_key: str) -> SupersededTraceLink:
        return self._execute(command, idempotency_key=idempotency_key)

    def _execute(self, command: SupersedeTraceLink | SupersedeTraceLinkRefs, *,
                 idempotency_key: str) -> SupersededTraceLink:
        if (type(command) not in (SupersedeTraceLink, SupersedeTraceLinkRefs)
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.trace_link_id))
                or type(command.expected_version) is not int
                or command.expected_version < 0):
            raise TraceSupersedeError("VALIDATION_FAILED")
        public = type(command) is SupersedeTraceLinkRefs
        if public:
            if (type(command.source) is not TraceResourceVersionRef
                    or type(command.target) is not TraceResourceVersionRef
                    or type(command.relation_type) is not str
                    or not command.relation_type
                    or any(type(ref.resource_type) is not str
                           or not ref.resource_type
                           or type(ref.resource_id) is not uuid.UUID
                           or ref.resource_id.int == 0
                           or type(ref.version_id) is not uuid.UUID
                           or ref.version_id.int == 0
                           for ref in (command.source, command.target))
                    or self._public_resolver is None):
                raise TraceSupersedeError("VALIDATION_FAILED")
            fingerprint_input = {
                "trace_link_id": str(command.trace_link_id),
                "expected_version": command.expected_version,
                "source": {
                    "resource_type": command.source.resource_type,
                    "resource_id": str(command.source.resource_id),
                    "version_id": str(command.source.version_id),
                },
                "target": {
                    "resource_type": command.target.resource_type,
                    "resource_id": str(command.target.resource_id),
                    "version_id": str(command.target.version_id),
                },
                "relation_type": command.relation_type,
            }
        else:
            if (type(command.replacement) is not TraceEdgeShape
                    or command.replacement.scope != "PROJECT"
                    or command.replacement.project_id != command.project_id):
                raise TraceSupersedeError("VALIDATION_FAILED")
            fingerprint_input = {
                "trace_link_id": str(command.trace_link_id),
                "expected_version": command.expected_version,
                "source": _ref_fingerprint(command.replacement.source),
                "target": _ref_fingerprint(command.replacement.target),
                "relation_type": command.replacement.relation_type,
            }
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint(fingerprint_input)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise TraceSupersedeError("TRACE_UNAVAILABLE")
                actor = self._sessions.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise TraceSupersedeError("AUTH_ACCESS_DENIED")
                action = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="TRACE_LINK_SUPERSEDE",
                )
                if (type(action) is not AuthorizedProjectAction
                        or action.user_id != actor
                        or action.project_id != command.project_id
                        or action.project_role != "PROJECT_MANAGER"):
                    raise TraceSupersedeError("RESOURCE_NOT_FOUND")
                state = self._repository.lock(
                    tx, project_id=command.project_id,
                    trace_link_id=command.trace_link_id,
                )
                if (type(state) is not TraceSupersedeState
                        or state.trace_link_id != command.trace_link_id
                        or state.project_id != command.project_id):
                    raise TraceSupersedeError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != _RESULT_TYPE or replay.status_code != 201
                            or state.link_state != "SUPERSEDED"
                            or state.lock_version != 1
                            or state.superseded_by_ref != replay.ref_id):
                        raise TraceSupersedeError("TRACE_UNAVAILABLE")
                    return SupersededTraceLink(state.trace_link_id, replay.ref_id, 1)
                if state.lock_version != command.expected_version:
                    raise TraceSupersedeError("CONFLICT_VERSION")
                if state.link_state != "ACTIVE":
                    raise TraceSupersedeError("CONFLICT_STATE")
                replacement = (self._public_resolver.resolve_edge(
                    tx, TraceProofQuery(command.session_token, command.trace_id),
                    command.project_id, command.source, command.target,
                    command.relation_type,
                ) if public else command.replacement)
                if (state.edge == replacement
                        or state.edge.source != replacement.source
                        and state.edge.target != replacement.target):
                    raise TraceSupersedeError("VALIDATION_FAILED")
                self._proofs.prove_edge(
                    tx, TraceProofQuery(command.session_token, command.trace_id),
                    replacement,
                )
                self._cycles.assert_acyclic(tx, replacement)
                stored = self._repository.create_active(
                    tx, edge=replacement, actor_id=actor,
                    trace_id=command.trace_id,
                )
                if (type(stored) is not StoredTraceLink
                        or type(stored.trace_link_id) is not uuid.UUID
                        or stored.trace_link_id.int == 0
                        or stored.inserted is not True):
                    raise TraceSupersedeError("CONFLICT_STATE")
                version = self._repository.supersede(
                    tx, project_id=command.project_id,
                    trace_link_id=command.trace_link_id,
                    expected_version=command.expected_version,
                    replacement_id=stored.trace_link_id,
                )
                if type(version) is not int or version != 1:
                    raise TraceSupersedeError("TRACE_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="TRACE_LINK_CREATED", outcome="SUCCESS",
                    target_owner_module="trace", target_object_type="TRC-01",
                    target_object_id=stored.trace_link_id, after_state="ACTIVE",
                ))
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="TRACE_LINK_SUPERSEDED", outcome="SUCCESS",
                    target_owner_module="trace", target_object_type="TRC-01",
                    target_object_id=command.trace_link_id,
                    before_state="ACTIVE", after_state="SUPERSEDED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(
                        _RESULT_TYPE, stored.trace_link_id, 201,
                    ),
                )
                tx.commit()
                return SupersededTraceLink(command.trace_link_id,
                                            stored.trace_link_id, version)
        except TraceSupersedeError:
            raise
        except RuntimeLicenseError:
            raise TraceSupersedeError("LICENSE_OPERATION_DENIED") from None
        except (IdempotencyError, ProjectAuthorizationError,
                TraceTargetProofError) as exc:
            raise TraceSupersedeError(exc.code) from None
        except TraceCycleError:
            raise TraceSupersedeError("CONFLICT_STATE") from None
        except Exception:
            raise TraceSupersedeError("TRACE_UNAVAILABLE") from None
