"""Authorized atomic creation of a logical SolutionOutline identity."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


_OPERATION = "V1_SOL_OUTLINE_CREATE"


class OutlineCreateError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateOutline:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class OutlineInitialView:
    solution_outline_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    outline_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (
            type(self.solution_outline_id) is not uuid.UUID
            or self.solution_outline_id.int == 0
            or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
            or type(self.name) is not str or not self.name
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
            or self.outline_state != "ACTIVE"
            or self.current_approved_version_ref is not None
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial SolutionOutline view")


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, outline_id: uuid.UUID,
               project_id: uuid.UUID, name: str, actor_id: uuid.UUID) -> OutlineInitialView: ...

    def first_result(self, transaction: object, *, outline_id: uuid.UUID,
                     project_id: uuid.UUID) -> OutlineInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class OutlineCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort, authorization: ProjectAuthorizationService,
                 repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("SolutionOutline create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repo = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateOutline) -> OutlineInitialView:
        if (
            type(command) is not CreateOutline
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
        ):
            raise OutlineCreateError("VALIDATION_FAILED")
        name = self._name(command.name)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id), "name": name,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SOL_OUTLINE_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SOL_OUTLINE_CREATE"):
                    raise OutlineCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise OutlineCreateError()
                    result = self._repo.first_result(
                        tx, outline_id=previous.ref_id, project_id=command.project_id)
                    if result is None or result.name != name:
                        raise OutlineCreateError()
                    return result
                outline_id = uuid.UUID(new_uuid7())
                result = self._repo.create(
                    tx, outline_id=outline_id, project_id=command.project_id,
                    name=name, actor_id=actor)
                if (type(result) is not OutlineInitialView
                        or result.solution_outline_id != outline_id
                        or result.project_id != command.project_id or result.name != name):
                    raise OutlineCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SOL_OUTLINE_CREATED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-02",
                    target_object_id=outline_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, outline_id, 201))
                tx.commit()
                return result
        except OutlineCreateError:
            raise
        except (ProjectAuthorizationError, IdempotencyError) as error:
            raise OutlineCreateError(error.code) from None
        except RuntimeLicenseError:
            raise OutlineCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise OutlineCreateError() from None

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise OutlineCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= 500
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise OutlineCreateError("VALIDATION_FAILED")
        return result

    def _actor(self, tx: object, command: CreateOutline) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise OutlineCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise OutlineCreateError("AUTH_ACCESS_DENIED")
        return actor
