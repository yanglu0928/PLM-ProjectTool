"""Authorized IN_PROGRESS to SUBMITTED Handover Action command."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .source_validation import (
    HandoverDocumentRef, HandoverSourceValidationError, HandoverSourceValidator,
)


_OPERATION = "V1_HND_ACTION_SUBMIT"


class HandoverActionSubmitError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SubmitHandoverAction:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    action_item_id: uuid.UUID
    expected_version: int
    response_documents: tuple[HandoverDocumentRef, ...]
    evidence_refs: tuple[uuid.UUID, ...]
    reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverActionSubmitLock:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    lock_version: int


@dataclass(frozen=True, slots=True)
class HandoverActionSubmitView:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    action_state_event_id: uuid.UUID
    action_state: str
    submitted_at: datetime
    response_documents: tuple[HandoverDocumentRef, ...]
    evidence_refs: tuple[uuid.UUID, ...]
    etag: str


class HandoverActionSubmitRepositoryPort(Protocol):
    def lock(self, transaction: object, *, command: SubmitHandoverAction,
             actor_id: uuid.UUID,
             actor_role: str) -> HandoverActionSubmitLock: ...
    def submit(self, transaction: object, *, command: SubmitHandoverAction,
               action: HandoverActionSubmitLock, actor_id: uuid.UUID,
               occurred_at: datetime) -> HandoverActionSubmitView: ...
    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID,
               actor_role: str) -> HandoverActionSubmitView | None: ...


class HandoverActionSubmissionEvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class HandoverActionSubmitService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 sources: HandoverSourceValidator,
                 evidence: HandoverActionSubmissionEvidencePort,
                 repository: HandoverActionSubmitRepositoryPort, receipts: object,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        values = (unit_of_work, access, license_guard, authorization, sources,
                  evidence, repository, receipts, audit)
        if any(value is None for value in values):
            raise ValueError("Handover Action submit dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources = authorization, sources
        self._evidence, self._repository = evidence, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def submit(self, command: SubmitHandoverAction) -> HandoverActionSubmitView:
        payload = self._validate_and_payload(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint(payload)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now = self._now()
                actor = self._access.authenticated_user(
                    tx, session_token=command.session_token,
                    csrf_token=command.csrf_token, now=now,
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise HandoverActionSubmitError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="HND_ACTION_SUBMIT",
                )
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise HandoverActionSubmitError()
                    view = self._repository.replay(
                        tx, action_item_id=command.action_item_id,
                        project_id=command.project_id, event_id=replay.ref_id,
                        actor_id=actor, actor_role=authorized.project_role,
                    )
                    if view is None:
                        raise HandoverActionSubmitError()
                    return view
                action = self._repository.lock(
                    tx, command=command, actor_id=actor,
                    actor_role=authorized.project_role,
                )
                self._sources.validate(
                    tx, project_id=command.project_id,
                    references=command.response_documents,
                )
                self._validate_evidence(tx, command)
                view = self._repository.submit(
                    tx, command=command, action=action,
                    actor_id=actor, occurred_at=now,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="HND_ACTION_SUBMITTED", outcome="SUCCESS",
                    target_owner_module="handover", target_object_type="HND-03",
                    target_object_id=command.action_item_id,
                    before_state="IN_PROGRESS", after_state="SUBMITTED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(
                        _OPERATION, view.action_state_event_id, 200,
                    ),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return view
        except HandoverActionSubmitError:
            raise
        except HandoverSourceValidationError:
            raise HandoverActionSubmitError("HANDOVER_SOURCE_REQUIRED") from None
        except ProjectAuthorizationError as error:
            raise HandoverActionSubmitError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverActionSubmitError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverActionSubmitError(error.code) from None
        except Exception:
            raise HandoverActionSubmitError() from None

    @staticmethod
    def _validate_and_payload(command: SubmitHandoverAction) -> dict[str, object]:
        if (type(command) is not SubmitHandoverAction
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.action_item_id) is not uuid.UUID or command.action_item_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0
                or type(command.response_documents) is not tuple
                or not 1 <= len(command.response_documents) <= 500
                or any(type(item) is not HandoverDocumentRef
                       for item in command.response_documents)
                or len({item.document_id for item in command.response_documents})
                   != len(command.response_documents)
                or len({item.document_version_id for item in command.response_documents})
                   != len(command.response_documents)
                or type(command.evidence_refs) is not tuple
                or not 1 <= len(command.evidence_refs) <= 500
                or any(type(item) is not uuid.UUID or item.int == 0
                       for item in command.evidence_refs)
                or len(set(command.evidence_refs)) != len(command.evidence_refs)
                or type(command.reason) is not str or not 1 <= len(command.reason) <= 2000
                or command.reason != command.reason.strip()):
            raise HandoverActionSubmitError("VALIDATION_FAILED")
        return {
            "project_id": str(command.project_id),
            "action_item_id": str(command.action_item_id),
            "expected_version": command.expected_version,
            "response_documents": [{
                "document_id": str(item.document_id),
                "document_version_id": str(item.document_version_id),
            } for item in command.response_documents],
            "evidence_refs": [str(item) for item in command.evidence_refs],
            "reason": command.reason,
        }

    def _validate_evidence(self, tx: object, command: SubmitHandoverAction) -> None:
        response_pairs = {
            (item.document_id, item.document_version_id)
            for item in command.response_documents
        }
        for evidence_id in command.evidence_refs:
            source = self._evidence.get_for_trace(
                tx, scope="PROJECT", project_id=command.project_id,
                evidence_id=evidence_id,
            )
            if (type(source) is not LockedEvidenceSource
                    or source.evidence_id != evidence_id
                    or source.scope != "PROJECT"
                    or source.project_id != command.project_id
                    or (source.document_id, source.document_version_id)
                       not in response_pairs
                    or type(source.content_fingerprint) is not bytes
                    or len(source.content_fingerprint) != 32
                    or type(source.lock_version) is not int
                    or source.lock_version < 0):
                raise HandoverActionSubmitError(
                    "HANDOVER_ACTION_EVIDENCE_REQUIRED",
                )

    def _now(self) -> datetime:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverActionSubmitError()
        return now.astimezone(timezone.utc)
