"""Authorized atomic creation of a logical project Plan identity."""

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


_OPERATION = "V1_PLAN_CREATE"


class PlanCreateError(RuntimeError):
    def __init__(self, code: str = "PLAN_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreatePlan:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PlanInitialView:
    plan_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    plan_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (
            type(self.plan_id) is not uuid.UUID or self.plan_id.int == 0
            or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
            or type(self.name) is not str or not self.name
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None or self.created_at.utcoffset() is None
            or self.plan_state != "ACTIVE"
            or self.current_approved_version_ref is not None
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial Plan view")


class AccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create(self, transaction: object, *, plan_id: uuid.UUID,
               project_id: uuid.UUID, name: str, actor_id: uuid.UUID) -> PlanInitialView: ...

    def first_result(self, transaction: object, *, plan_id: uuid.UUID,
                     project_id: uuid.UUID) -> PlanInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class PlanCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AccessPort,
                 license_guard: LicensePort, authorization: ProjectAuthorizationService,
                 repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("Plan create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repo = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreatePlan) -> PlanInitialView:
        if (
            type(command) is not CreatePlan
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
        ):
            raise PlanCreateError("VALIDATION_FAILED")
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
                    operation="PLAN_CREATE")
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "PLAN_CREATE"):
                    raise PlanCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key)
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if previous is not None:
                    if previous.ref_type != _OPERATION or previous.status_code != 201:
                        raise PlanCreateError()
                    result = self._repo.first_result(
                        tx, plan_id=previous.ref_id, project_id=command.project_id)
                    if result is None or result.name != name:
                        raise PlanCreateError()
                    return result
                plan_id = uuid.UUID(new_uuid7())
                result = self._repo.create(
                    tx, plan_id=plan_id, project_id=command.project_id,
                    name=name, actor_id=actor)
                if (type(result) is not PlanInitialView or result.plan_id != plan_id
                        or result.project_id != command.project_id or result.name != name):
                    raise PlanCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="PLAN_CREATED", outcome="SUCCESS",
                    target_owner_module="plan", target_object_type="PLN-01",
                    target_object_id=plan_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(_OPERATION, plan_id, 201))
                tx.commit()
                return result
        except PlanCreateError:
            raise
        except (ProjectAuthorizationError, IdempotencyError) as error:
            raise PlanCreateError(error.code) from None
        except RuntimeLicenseError:
            raise PlanCreateError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PlanCreateError() from None

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise PlanCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= 500
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise PlanCreateError("VALIDATION_FAILED")
        return result

    def _actor(self, tx: object, command: CreatePlan) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PlanCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PlanCreateError("AUTH_ACCESS_DENIED")
        return actor
