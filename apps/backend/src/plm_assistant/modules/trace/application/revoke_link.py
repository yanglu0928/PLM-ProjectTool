"""Internal PROJECT TraceLink revoke with current PM authority and atomic history."""

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


_OPERATION = "V1_TRACE_LINK_REVOKE"
_RESULT_TYPE = "V1_TRACE_LINK_REVOKED"


class TraceRevokeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RevokeTraceLink:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    trace_link_id: uuid.UUID
    expected_version: int


@dataclass(frozen=True, slots=True)
class RevokedTraceLink:
    trace_link_id: uuid.UUID
    lock_version: int


@dataclass(frozen=True, slots=True)
class TraceLinkState:
    trace_link_id: uuid.UUID
    project_id: uuid.UUID
    link_state: str
    lock_version: int


class TraceRevokeSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class TraceRevokeProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class TraceRevokeLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class TraceRevokeRepositoryPort(Protocol):
    def lock(self, transaction: object, *, project_id: uuid.UUID,
             trace_link_id: uuid.UUID) -> TraceLinkState | None: ...
    def revoke(self, transaction: object, *, project_id: uuid.UUID,
               trace_link_id: uuid.UUID, expected_version: int) -> int: ...


class TraceRevokeReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class TraceRevokeService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 sessions: TraceRevokeSessionPort,
                 projects: TraceRevokeProjectPort,
                 license_guard: TraceRevokeLicensePort,
                 repository: TraceRevokeRepositoryPort,
                 receipts: TraceRevokeReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, sessions, projects, license_guard,
                repository, receipts, audit)):
            raise ValueError("Trace revoke dependencies are required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._repository = license_guard, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revoke(self, command: RevokeTraceLink, *,
               idempotency_key: str) -> RevokedTraceLink:
        if (type(command) is not RevokeTraceLink
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.trace_link_id))
                or type(command.expected_version) is not int
                or command.expected_version < 0):
            raise TraceRevokeError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "trace_link_id": str(command.trace_link_id),
                "expected_version": command.expected_version,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise TraceRevokeError("TRACE_UNAVAILABLE")
                actor = self._sessions.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise TraceRevokeError("AUTH_ACCESS_DENIED")
                action = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="TRACE_LINK_REVOKE",
                )
                if (type(action) is not AuthorizedProjectAction
                        or action.user_id != actor
                        or action.project_id != command.project_id
                        or action.project_role != "PROJECT_MANAGER"):
                    raise TraceRevokeError("RESOURCE_NOT_FOUND")
                state = self._repository.lock(
                    tx, project_id=command.project_id,
                    trace_link_id=command.trace_link_id,
                )
                if (type(state) is not TraceLinkState
                        or state.trace_link_id != command.trace_link_id
                        or state.project_id != command.project_id):
                    raise TraceRevokeError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != _RESULT_TYPE
                            or replay.ref_id != command.trace_link_id
                            or replay.status_code != 200
                            or state.link_state != "REVOKED"
                            or state.lock_version != 1):
                        raise TraceRevokeError("TRACE_UNAVAILABLE")
                    return RevokedTraceLink(replay.ref_id, 1)
                if state.lock_version != command.expected_version:
                    raise TraceRevokeError("CONFLICT_VERSION")
                if state.link_state != "ACTIVE":
                    raise TraceRevokeError("CONFLICT_STATE")
                new_version = self._repository.revoke(
                    tx, project_id=command.project_id,
                    trace_link_id=command.trace_link_id,
                    expected_version=command.expected_version,
                )
                if type(new_version) is not int or new_version != 1:
                    raise TraceRevokeError("TRACE_UNAVAILABLE")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="TRACE_LINK_REVOKED", outcome="SUCCESS",
                    target_owner_module="trace", target_object_type="TRC-01",
                    target_object_id=command.trace_link_id,
                    before_state="ACTIVE", after_state="REVOKED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(
                        _RESULT_TYPE, command.trace_link_id, 200,
                    ),
                )
                tx.commit()
                return RevokedTraceLink(command.trace_link_id, new_version)
        except TraceRevokeError:
            raise
        except RuntimeLicenseError:
            raise TraceRevokeError("LICENSE_OPERATION_DENIED") from None
        except (IdempotencyError, ProjectAuthorizationError) as exc:
            raise TraceRevokeError(exc.code) from None
        except Exception:
            raise TraceRevokeError("TRACE_UNAVAILABLE") from None
