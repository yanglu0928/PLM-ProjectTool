"""Authorized, atomic Survey identity creation."""

from __future__ import annotations

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


_OPERATION = "V1_SURVEY_CREATE"


class SurveyCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSurvey:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SurveyInitialView:
    survey_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    survey_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (type(self.survey_id) is not uuid.UUID or self.survey_id.int == 0
                or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
                or type(self.name) is not str or not self.name
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None
                or self.created_at.utcoffset() is None
                or self.survey_state != "ACTIVE"
                or self.current_approved_version_ref is not None
                or self.etag != '"v0"'):
            raise ValueError("invalid initial Survey view")


class SurveyCreateAccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class SurveyCreateLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SurveyCreateRepositoryPort(Protocol):
    def create(
        self, transaction: object, *, survey_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> None: ...

    def initial_view(
        self, transaction: object, *, survey_id: uuid.UUID,
        project_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyInitialView | None: ...


class SurveyCreateReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class SurveyCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: SurveyCreateAccessPort,
        license_guard: SurveyCreateLicensePort,
        authorization: ProjectAuthorizationService,
        repository: SurveyCreateRepositoryPort,
        receipts: SurveyCreateReceiptPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("SurveyCreate dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSurvey) -> SurveyInitialView:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "name": command.name,
            })
            survey_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor_id, project_id=command.project_id,
                    operation="SURVEY_CREATE",
                )
                if (authorized.user_id != actor_id
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
                    raise SurveyCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyCreateError("SURVEY_UNAVAILABLE")
                    view = self._repository.initial_view(
                        tx, survey_id=replay.ref_id,
                        project_id=command.project_id, actor_id=actor_id,
                    )
                    if not self._matches(view, command):
                        raise SurveyCreateError("SURVEY_UNAVAILABLE")
                    return view
                self._repository.create(
                    tx, survey_id=survey_id, project_id=command.project_id,
                    name=command.name, actor_id=actor_id,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_CREATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-01",
                    target_object_id=survey_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, survey_id, 201),
                )
                view = self._repository.initial_view(
                    tx, survey_id=survey_id, project_id=command.project_id,
                    actor_id=actor_id,
                )
                if not self._matches(view, command):
                    raise SurveyCreateError("SURVEY_UNAVAILABLE")
                tx.commit()
                return view
        except SurveyCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyCreateError(error.code) from None
        except Exception:
            raise SurveyCreateError("SURVEY_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: CreateSurvey) -> None:
        if (type(command) is not CreateSurvey
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID
                or command.project_id.int == 0
                or type(command.name) is not str
                or not 1 <= len(command.name) <= 255
                or command.name != command.name.strip()):
            raise SurveyCreateError("VALIDATION_FAILED")

    def _actor(self, tx: object, command: CreateSurvey) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyCreateError("SURVEY_UNAVAILABLE")
        actor_id = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise SurveyCreateError("AUTH_ACCESS_DENIED")
        return actor_id

    @staticmethod
    def _matches(view: SurveyInitialView | None, command: CreateSurvey) -> bool:
        return (type(view) is SurveyInitialView
                and view.project_id == command.project_id
                and view.name == command.name)
