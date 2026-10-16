"""Authorized Handover Analysis metadata and archive commands."""

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
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .read_analyses import HandoverAnalysisView


_ARCHIVE_OPERATION = "V1_HND_ANALYSIS_ARCHIVE"


class HandoverAnalysisStateError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchHandoverAnalysis:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    expected_lock_version: int
    analysis_purpose: str


@dataclass(frozen=True, slots=True)
class ArchiveHandoverAnalysis:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


class HandoverAnalysisStateRepositoryPort(Protocol):
    def get(self, transaction: object, *, project_id: uuid.UUID,
            handover_analysis_id: uuid.UUID) -> HandoverAnalysisView | None: ...
    def patch(self, transaction: object, *, project_id: uuid.UUID,
              handover_analysis_id: uuid.UUID, expected_lock_version: int,
              analysis_purpose: str,
              actor_id: uuid.UUID) -> HandoverAnalysisView: ...
    def archive(self, transaction: object, *, project_id: uuid.UUID,
                handover_analysis_id: uuid.UUID, expected_lock_version: int,
                actor_id: uuid.UUID) -> HandoverAnalysisView: ...


class HandoverAnalysisStateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: HandoverAnalysisStateRepositoryPort,
                 receipts: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("Handover Analysis state dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchHandoverAnalysis) -> HandoverAnalysisView:
        self._validate_common(command, PatchHandoverAnalysis)
        purpose = self._purpose(command.analysis_purpose)
        return self._execute(command, "HND_ANALYSIS_PATCH", lambda tx, actor:
            self._patch(tx, actor, command, purpose))

    def archive(self, command: ArchiveHandoverAnalysis) -> HandoverAnalysisView:
        self._validate_common(command, ArchiveHandoverAnalysis)
        try:
            validate_idempotency_key(command.idempotency_key)
        except IdempotencyError:
            raise HandoverAnalysisStateError("VALIDATION_FAILED") from None
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(command.project_id),
            "handover_analysis_id": str(command.handover_analysis_id),
            "expected_lock_version": command.expected_lock_version,
        })
        return self._execute(command, "HND_ANALYSIS_ARCHIVE", lambda tx, actor:
            self._archive(tx, actor, command, fingerprint))

    def _patch(self, tx: object, actor: uuid.UUID,
               command: PatchHandoverAnalysis,
               purpose: str) -> HandoverAnalysisView:
        result = self._repository.patch(
            tx, project_id=command.project_id,
            handover_analysis_id=command.handover_analysis_id,
            expected_lock_version=command.expected_lock_version,
            analysis_purpose=purpose, actor_id=actor,
        )
        self._append_audit(
            tx, command, actor, action="HND_ANALYSIS_PATCHED",
            before_state="ACTIVE", after_state="ACTIVE",
            reason_code="METADATA_UPDATED",
        )
        return result

    def _archive(self, tx: object, actor: uuid.UUID,
                 command: ArchiveHandoverAnalysis,
                 fingerprint: bytes) -> HandoverAnalysisView:
        scope = IdempotencyScope.from_key(
            actor_id=actor, project_id=command.project_id,
            operation=_ARCHIVE_OPERATION, key=command.idempotency_key,
        )
        replay = self._receipts.reserve(
            tx, scope=scope, request_fingerprint=fingerprint,
        )
        if replay is not None:
            if (type(replay) is not IdempotencyResult
                    or replay.ref_type != _ARCHIVE_OPERATION
                    or replay.ref_id != command.handover_analysis_id
                    or replay.status_code != 200):
                raise HandoverAnalysisStateError()
            result = self._repository.get(
                tx, project_id=command.project_id,
                handover_analysis_id=command.handover_analysis_id,
            )
            if (type(result) is not HandoverAnalysisView
                    or result.analysis_state != "ARCHIVED"
                    or result.etag != f'"v{command.expected_lock_version + 1}"'):
                raise HandoverAnalysisStateError()
            return result
        result = self._repository.archive(
            tx, project_id=command.project_id,
            handover_analysis_id=command.handover_analysis_id,
            expected_lock_version=command.expected_lock_version,
            actor_id=actor,
        )
        self._append_audit(
            tx, command, actor, action="HND_ANALYSIS_ARCHIVED",
            before_state="ACTIVE", after_state="ARCHIVED",
        )
        self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
            _ARCHIVE_OPERATION, command.handover_analysis_id, 200,
        ))
        return result

    def _append_audit(self, tx: object, command: object, actor: uuid.UUID,
                      *, action: str, before_state: str, after_state: str,
                      reason_code: str | None = None) -> None:
        audit_id = self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",  # type: ignore[attr-defined]
            target_project_id=command.project_id, actor_type="USER",  # type: ignore[attr-defined]
            actor_id=actor, original_actor_id=None, actor_hint_digest=None,
            action=action, outcome="SUCCESS", target_owner_module="handover",
            target_object_type="HND-01",
            target_object_id=command.handover_analysis_id,  # type: ignore[attr-defined]
            reason_code=reason_code, before_state=before_state,
            after_state=after_state,
        ))
        if type(audit_id) is not uuid.UUID or audit_id.int == 0:
            raise HandoverAnalysisStateError()

    def _execute(self, command: object, operation: str,
                 action: Callable[[object, uuid.UUID], HandoverAnalysisView]
                 ) -> HandoverAnalysisView:
        try:
            self._guard.require_valid(trace_id=command.trace_id)  # type: ignore[attr-defined]
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,  # type: ignore[attr-defined]
                    operation=operation,
                )
                if (authorized.user_id != actor
                        or authorized.project_id != command.project_id  # type: ignore[attr-defined]
                        or authorized.operation != operation):
                    raise HandoverAnalysisStateError("RESOURCE_NOT_FOUND")
                result = action(tx, actor)
                if type(result) is not HandoverAnalysisView:
                    raise HandoverAnalysisStateError()
                self._guard.require_valid(trace_id=command.trace_id)  # type: ignore[attr-defined]
                tx.commit()
                return result
        except HandoverAnalysisStateError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverAnalysisStateError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverAnalysisStateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverAnalysisStateError(error.code) from None
        except Exception:
            raise HandoverAnalysisStateError() from None

    def _actor(self, tx: object, command: object) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise HandoverAnalysisStateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,  # type: ignore[attr-defined]
            csrf_token=command.csrf_token,  # type: ignore[attr-defined]
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise HandoverAnalysisStateError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _validate_common(command: object, command_type: type) -> None:
        if (type(command) is not command_type
                or type(command.session_token) is not bytes  # type: ignore[attr-defined]
                or len(command.session_token) != 32  # type: ignore[attr-defined]
                or type(command.csrf_token) is not bytes  # type: ignore[attr-defined]
                or len(command.csrf_token) != 32  # type: ignore[attr-defined]
                or type(command.trace_id) is not uuid.UUID  # type: ignore[attr-defined]
                or command.trace_id.int == 0  # type: ignore[attr-defined]
                or type(command.project_id) is not uuid.UUID  # type: ignore[attr-defined]
                or command.project_id.int == 0  # type: ignore[attr-defined]
                or type(command.handover_analysis_id) is not uuid.UUID  # type: ignore[attr-defined]
                or command.handover_analysis_id.int == 0  # type: ignore[attr-defined]
                or type(command.expected_lock_version) is not int  # type: ignore[attr-defined]
                or not 0 <= command.expected_lock_version <= 9223372036854775806):  # type: ignore[attr-defined]
            raise HandoverAnalysisStateError("VALIDATION_FAILED")

    @staticmethod
    def _purpose(value: object) -> str:
        if type(value) is not str:
            raise HandoverAnalysisStateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= 255
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise HandoverAnalysisStateError("VALIDATION_FAILED")
        return result
