"""Authorized Survey Round schedule and lifecycle commands."""

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
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)

from .round_views import SurveyRoundView
from .round_completeness import (
    SurveyRoundCompletenessError,
    SurveyRoundCompletenessOwner,
    SurveyRoundCompletenessProof,
    SurveyRoundCompletenessQuery,
)


_OPEN_OPERATION = "V1_SURVEY_ROUND_OPEN"
_CLOSE_OPERATION = "V1_SURVEY_ROUND_CLOSE"
_CANCEL_OPERATION = "V1_SURVEY_ROUND_CANCEL"


class SurveyRoundStateError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ROUND_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchSurveyRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    expected_lock_version: int
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    location_note: str | None


@dataclass(frozen=True, slots=True)
class OpenSurveyRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CancelSurveyRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    expected_lock_version: int
    reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CloseSurveyRound:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


class RepositoryPort(Protocol):
    def get(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID,
    ) -> SurveyRoundView | None: ...

    def patch(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        scheduled_start_at: datetime | None,
        scheduled_end_at: datetime | None, location_note: str | None,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView: ...

    def open(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        actor_id: uuid.UUID,
    ) -> SurveyRoundView: ...

    def cancel(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        reason: str, actor_id: uuid.UUID,
    ) -> SurveyRoundView: ...

    def close(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID, expected_lock_version: int,
        report_fingerprint: bytes, actor_id: uuid.UUID,
    ) -> SurveyRoundView: ...


class SurveyRoundStateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: RepositoryPort, receipts: object, audit: AuditService,
        completeness: SurveyRoundCompletenessOwner | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("Survey Round state dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._completeness = completeness
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchSurveyRound) -> SurveyRoundView:
        self._validate_common(command, PatchSurveyRound)
        start, end = self._schedule(
            command.scheduled_start_at, command.scheduled_end_at,
        )
        location = self._text(command.location_note, maximum=1000, optional=True)
        return self._execute(command, "SURVEY_ROUND_PATCH", lambda tx, authorized:
            self._patch(tx, authorized.user_id, command, start, end, location))

    def open(self, command: OpenSurveyRound) -> SurveyRoundView:
        self._validate_common(command, OpenSurveyRound)
        fingerprint = self._idempotency_fingerprint(command, {})
        return self._execute(command, "SURVEY_ROUND_OPEN", lambda tx, authorized:
            self._transition(
                tx, authorized.user_id, command, fingerprint=fingerprint,
                operation=_OPEN_OPERATION, final_state="OPEN",
                action="SURVEY_ROUND_OPENED",
                apply=lambda: self._repository.open(
                    tx, project_id=command.project_id,
                    survey_round_id=command.survey_round_id,
                    expected_lock_version=command.expected_lock_version,
                    actor_id=authorized.user_id,
                ),
            ))

    def cancel(self, command: CancelSurveyRound) -> SurveyRoundView:
        self._validate_common(command, CancelSurveyRound)
        reason = self._text(command.reason, maximum=2000, optional=False)
        fingerprint = self._idempotency_fingerprint(command, {"reason": reason})
        return self._execute(command, "SURVEY_ROUND_CANCEL", lambda tx, authorized:
            self._transition(
                tx, authorized.user_id, command, fingerprint=fingerprint,
                operation=_CANCEL_OPERATION, final_state="CANCELLED",
                action="SURVEY_ROUND_CANCELLED", reason_code="USER_CANCELLED",
                apply=lambda: self._repository.cancel(
                    tx, project_id=command.project_id,
                    survey_round_id=command.survey_round_id,
                    expected_lock_version=command.expected_lock_version,
                    reason=reason, actor_id=authorized.user_id,
                ),
            ))

    def close(self, command: CloseSurveyRound) -> SurveyRoundView:
        self._validate_common(command, CloseSurveyRound)
        fingerprint = self._idempotency_fingerprint(command, {})
        return self._execute(command, "SURVEY_ROUND_CLOSE", lambda tx, authorized:
            self._transition(
                tx, authorized.user_id, command, fingerprint=fingerprint,
                operation=_CLOSE_OPERATION, final_state="CLOSED",
                action="SURVEY_ROUND_CLOSED", before_state="OPEN",
                apply=lambda: self._apply_close(tx, authorized, command),
            ))

    def _apply_close(
        self, tx: object, authorized: AuthorizedProjectAction,
        command: CloseSurveyRound,
    ) -> SurveyRoundView:
        if self._completeness is None:
            raise SurveyRoundStateError("SURVEY_ROUND_COMPLETENESS_UNAVAILABLE")
        try:
            proof = self._completeness.prove(tx, SurveyRoundCompletenessQuery(
                command.session_token, command.trace_id, command.project_id,
                command.survey_round_id, authorized.user_id,
                authorized.project_role,
            ))
        except SurveyRoundCompletenessError as error:
            raise SurveyRoundStateError(error.code) from None
        if (type(proof) is not SurveyRoundCompletenessProof
                or proof.project_id != command.project_id
                or proof.survey_round_id != command.survey_round_id
                or type(proof.report_fingerprint) is not bytes
                or len(proof.report_fingerprint) != 32):
            raise SurveyRoundStateError()
        return self._repository.close(
            tx, project_id=command.project_id,
            survey_round_id=command.survey_round_id,
            expected_lock_version=command.expected_lock_version,
            report_fingerprint=proof.report_fingerprint,
            actor_id=authorized.user_id,
        )

    def _patch(
        self, tx: object, actor: uuid.UUID, command: PatchSurveyRound,
        start: datetime | None, end: datetime | None, location: str | None,
    ) -> SurveyRoundView:
        result = self._repository.patch(
            tx, project_id=command.project_id,
            survey_round_id=command.survey_round_id,
            expected_lock_version=command.expected_lock_version,
            scheduled_start_at=start, scheduled_end_at=end,
            location_note=location, actor_id=actor,
        )
        self._append_audit(
            tx, command, actor, result, action="SURVEY_ROUND_PATCHED",
            before_state="PLANNED", after_state="PLANNED",
            reason_code="SCHEDULE_UPDATED",
        )
        return result

    def _transition(
        self, tx: object, actor: uuid.UUID, command: object, *,
        fingerprint: bytes, operation: str, final_state: str, action: str,
        apply: Callable[[], SurveyRoundView], reason_code: str | None = None,
        before_state: str = "PLANNED",
    ) -> SurveyRoundView:
        scope = IdempotencyScope.from_key(
            actor_id=actor, project_id=command.project_id,  # type: ignore[attr-defined]
            operation=operation, key=command.idempotency_key,  # type: ignore[attr-defined]
        )
        replay = self._receipts.reserve(
            tx, scope=scope, request_fingerprint=fingerprint,
        )
        if replay is not None:
            if (type(replay) is not IdempotencyResult
                    or replay.ref_type != operation
                    or replay.ref_id != command.survey_round_id  # type: ignore[attr-defined]
                    or replay.status_code != 200):
                raise SurveyRoundStateError()
            result = self._repository.get(
                tx, project_id=command.project_id,  # type: ignore[attr-defined]
                survey_round_id=command.survey_round_id,  # type: ignore[attr-defined]
            )
            if (type(result) is not SurveyRoundView
                    or result.round_state != final_state
                    or result.etag
                    != f'"v{command.expected_lock_version + 1}"'):  # type: ignore[attr-defined]
                raise SurveyRoundStateError()
            return result
        result = apply()
        self._append_audit(
            tx, command, actor, result, action=action,
            before_state=before_state, after_state=final_state,
            reason_code=reason_code,
        )
        self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
            operation, command.survey_round_id, 200,  # type: ignore[attr-defined]
        ))
        return result

    def _append_audit(
        self, tx: object, command: object, actor: uuid.UUID,
        result: SurveyRoundView, *, action: str, before_state: str,
        after_state: str, reason_code: str | None = None,
    ) -> None:
        audit_id = self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",  # type: ignore[attr-defined]
            target_project_id=command.project_id, actor_type="USER",  # type: ignore[attr-defined]
            actor_id=actor, original_actor_id=None, actor_hint_digest=None,
            action=action, outcome="SUCCESS", target_owner_module="survey",
            target_object_type="SRV-03",
            target_object_id=command.survey_round_id,  # type: ignore[attr-defined]
            target_version_id=result.survey_version_id,
            reason_code=reason_code, before_state=before_state,
            after_state=after_state,
        ))
        if type(audit_id) is not uuid.UUID or audit_id.int == 0:
            raise SurveyRoundStateError()

    def _execute(
        self, command: object, operation: str,
        action: Callable[[object, AuthorizedProjectAction], SurveyRoundView],
    ) -> SurveyRoundView:
        try:
            self._guard.require_valid(trace_id=command.trace_id)  # type: ignore[attr-defined]
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor,
                    project_id=command.project_id,  # type: ignore[attr-defined]
                    operation=operation,
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id  # type: ignore[attr-defined]
                        or authorized.operation != operation):
                    raise SurveyRoundStateError("RESOURCE_NOT_FOUND")
                if authorized.project_role not in (
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                    "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
                ):
                    raise SurveyRoundStateError("RESOURCE_NOT_FOUND")
                result = action(tx, authorized)
                if type(result) is not SurveyRoundView:
                    raise SurveyRoundStateError()
                self._guard.require_valid(trace_id=command.trace_id)  # type: ignore[attr-defined]
                tx.commit()
                return result
        except SurveyRoundStateError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyRoundStateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyRoundStateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyRoundStateError(error.code) from None
        except Exception:
            raise SurveyRoundStateError() from None

    def _actor(self, tx: object, command: object) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyRoundStateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,  # type: ignore[attr-defined]
            csrf_token=command.csrf_token,  # type: ignore[attr-defined]
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyRoundStateError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _validate_common(command: object, command_type: type) -> None:
        if (type(command) is not command_type
                or type(command.session_token) is not bytes  # type: ignore[attr-defined]
                or len(command.session_token) != 32  # type: ignore[attr-defined]
                or type(command.csrf_token) is not bytes  # type: ignore[attr-defined]
                or len(command.csrf_token) != 32  # type: ignore[attr-defined]
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id,  # type: ignore[attr-defined]
                    command.survey_round_id,  # type: ignore[attr-defined]
                ))
                or type(command.expected_lock_version) is not int  # type: ignore[attr-defined]
                or not 0 <= command.expected_lock_version <= 9223372036854775806):  # type: ignore[attr-defined]
            raise SurveyRoundStateError("VALIDATION_FAILED")

    def _idempotency_fingerprint(
        self, command: object, extra: dict[str, object],
    ) -> bytes:
        self._validate_key(command.idempotency_key)  # type: ignore[attr-defined]
        return canonical_payload_fingerprint({
            "project_id": str(command.project_id),  # type: ignore[attr-defined]
            "survey_round_id": str(command.survey_round_id),  # type: ignore[attr-defined]
            "expected_lock_version": command.expected_lock_version,  # type: ignore[attr-defined]
            **extra,
        })

    @staticmethod
    def _validate_key(value: object) -> None:
        try:
            validate_idempotency_key(value)  # type: ignore[arg-type]
        except IdempotencyError:
            raise SurveyRoundStateError("VALIDATION_FAILED") from None

    @staticmethod
    def _schedule(
        start: object, end: object,
    ) -> tuple[datetime | None, datetime | None]:
        if (start is None) != (end is None):
            raise SurveyRoundStateError("VALIDATION_FAILED")
        if start is None:
            return None, None
        if (type(start) is not datetime or start.tzinfo is None
                or start.utcoffset() is None or type(end) is not datetime
                or end.tzinfo is None or end.utcoffset() is None or end <= start):
            raise SurveyRoundStateError("VALIDATION_FAILED")
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    @staticmethod
    def _text(value: object, *, maximum: int, optional: bool) -> str | None:
        if value is None and optional:
            return None
        if type(value) is not str:
            raise SurveyRoundStateError("VALIDATION_FAILED")
        normalized = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(normalized) <= maximum
                or any(unicodedata.category(char)[0] == "C" for char in normalized)):
            raise SurveyRoundStateError("VALIDATION_FAILED")
        return normalized
