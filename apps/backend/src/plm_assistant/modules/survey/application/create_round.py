"""Authorized atomic creation of a PLANNED Survey Round."""

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
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)

from .round_views import SurveyRoundView


_OPERATION = "V1_SURVEY_ROUND_CREATE"


class SurveyRoundCreateError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ROUND_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSurveyRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_id: uuid.UUID
    survey_version_id: uuid.UUID
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    location_note: str | None
    idempotency_key: str = field(repr=False)


class AccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class RepositoryPort(Protocol):
    def create(
        self, transaction: object, *, survey_round_id: uuid.UUID,
        project_id: uuid.UUID, survey_id: uuid.UUID,
        survey_version_id: uuid.UUID, scheduled_start_at: datetime | None,
        scheduled_end_at: datetime | None, location_note: str | None,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView: ...

    def get_initial(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> SurveyRoundView | None: ...


class ReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class SurveyRoundCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: AccessPort,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("Survey Round create dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSurveyRound) -> SurveyRoundView:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            start = self._utc(command.scheduled_start_at)
            end = self._utc(command.scheduled_end_at)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_id": str(command.survey_id),
                "survey_version_id": str(command.survey_version_id),
                "scheduled_start_at": None if start is None else start.isoformat(),
                "scheduled_end_at": None if end is None else end.isoformat(),
                "location_note": command.location_note,
            })
            survey_round_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_ROUND_CREATE",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_ROUND_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                        )):
                    raise SurveyRoundCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyRoundCreateError()
                    view = self._repository.get_initial(
                        tx, project_id=command.project_id,
                        survey_round_id=replay.ref_id, actor_id=actor,
                    )
                    if not self._matches(view, command, start, end):
                        raise SurveyRoundCreateError()
                    return view
                view = self._repository.create(
                    tx, survey_round_id=survey_round_id,
                    project_id=command.project_id, survey_id=command.survey_id,
                    survey_version_id=command.survey_version_id,
                    scheduled_start_at=start, scheduled_end_at=end,
                    location_note=command.location_note, actor_id=actor,
                )
                if not self._matches(view, command, start, end):
                    raise SurveyRoundCreateError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_ROUND_CREATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-03",
                    target_object_id=survey_round_id,
                    target_version_id=command.survey_version_id,
                    after_state="PLANNED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, survey_round_id, 201),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except SurveyRoundCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyRoundCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyRoundCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyRoundCreateError(error.code) from None
        except Exception:
            raise SurveyRoundCreateError() from None

    @staticmethod
    def _validate(command: CreateSurveyRound) -> None:
        if (type(command) is not CreateSurveyRound
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.survey_id,
                    command.survey_version_id,
                ))
                or (command.scheduled_start_at is None)
                != (command.scheduled_end_at is None)
                or command.scheduled_start_at is not None and (
                    type(command.scheduled_start_at) is not datetime
                    or command.scheduled_start_at.tzinfo is None
                    or command.scheduled_start_at.utcoffset() is None
                    or type(command.scheduled_end_at) is not datetime
                    or command.scheduled_end_at.tzinfo is None
                    or command.scheduled_end_at.utcoffset() is None
                    or command.scheduled_end_at <= command.scheduled_start_at
                )
                or command.location_note is not None and (
                    type(command.location_note) is not str
                    or not 1 <= len(command.location_note) <= 1000
                    or command.location_note != command.location_note.strip()
                )):
            raise SurveyRoundCreateError("VALIDATION_FAILED")

    def _actor(self, tx: object, command: CreateSurveyRound) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyRoundCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyRoundCreateError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _utc(value: datetime | None) -> datetime | None:
        return None if value is None else value.astimezone(timezone.utc)

    @staticmethod
    def _matches(
        view: SurveyRoundView | None, command: CreateSurveyRound,
        start: datetime | None, end: datetime | None,
    ) -> bool:
        return (type(view) is SurveyRoundView
                and view.project_id == command.project_id
                and view.survey_id == command.survey_id
                and view.survey_version_id == command.survey_version_id
                and view.round_state == "PLANNED"
                and view.scheduled_start_at == start
                and view.scheduled_end_at == end
                and view.location_note == command.location_note
                and view.etag == '"v0"'
                and view.source_record_count == 0
                and view.source_records == ())
