"""Authorized, atomic HandoverAnalysis identity creation."""

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

from .source_validation import (
    HandoverDocumentRef, HandoverSourceValidationError, HandoverSourceValidator,
)


_OPERATION = "V1_HND_ANALYSIS_CREATE"


class HandoverAnalysisCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateHandoverAnalysis:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    analysis_purpose: str
    source_documents: tuple[HandoverDocumentRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class HandoverAnalysisInitialView:
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    analysis_purpose: str
    source_set_ref: str
    created_at: datetime
    analysis_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (type(self.handover_analysis_id) is not uuid.UUID
                or self.handover_analysis_id.int == 0
                or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
                or type(self.created_at) is not datetime or self.created_at.tzinfo is None
                or self.analysis_state != "ACTIVE"
                or self.current_approved_version_ref is not None
                or self.etag != '"v0"'):
            raise ValueError("invalid initial HandoverAnalysis view")


class HandoverAnalysisAccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class HandoverAnalysisLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class HandoverAnalysisRepositoryPort(Protocol):
    def create(
        self, transaction: object, *, handover_analysis_id: uuid.UUID,
        project_id: uuid.UUID, analysis_purpose: str,
        source_set_ref: str, actor_id: uuid.UUID,
    ) -> None: ...

    def initial_view(
        self, transaction: object, *, handover_analysis_id: uuid.UUID,
        project_id: uuid.UUID, actor_id: uuid.UUID,
    ) -> HandoverAnalysisInitialView | None: ...


class HandoverAnalysisReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class HandoverAnalysisCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: HandoverAnalysisAccessPort,
        license_guard: HandoverAnalysisLicensePort,
        authorization: ProjectAuthorizationService,
        sources: HandoverSourceValidator,
        repository: HandoverAnalysisRepositoryPort,
        receipts: HandoverAnalysisReceiptPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, authorization,
                sources, repository, receipts, audit)):
            raise ValueError("HandoverAnalysis dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._sources = authorization, sources
        self._repository, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateHandoverAnalysis) -> HandoverAnalysisInitialView:
        self._validate(command)
        ordered = tuple(sorted(
            command.source_documents, key=lambda item: str(item.document_version_id),
        ))
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "analysis_purpose": command.analysis_purpose,
                "source_documents": [{
                    "document_id": str(item.document_id),
                    "document_version_id": str(item.document_version_id),
                } for item in ordered],
            })
            handover_analysis_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor_id, project_id=command.project_id,
                    operation="HND_ANALYSIS_CREATE",
                )
                if (authorized.user_id != actor_id
                        or authorized.project_id != command.project_id
                        or authorized.operation != "HND_ANALYSIS_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
                    raise HandoverAnalysisCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise HandoverAnalysisCreateError("HANDOVER_UNAVAILABLE")
                    view = self._repository.initial_view(
                        tx, handover_analysis_id=replay.ref_id,
                        project_id=command.project_id, actor_id=actor_id,
                    )
                    if not self._matches(view, command):
                        raise HandoverAnalysisCreateError("HANDOVER_UNAVAILABLE")
                    return view
                validated = self._sources.validate(
                    tx, project_id=command.project_id, references=ordered,
                )
                self._repository.create(
                    tx, handover_analysis_id=handover_analysis_id,
                    project_id=command.project_id,
                    analysis_purpose=command.analysis_purpose,
                    source_set_ref=validated.source_set_ref, actor_id=actor_id,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="HND_ANALYSIS_CREATED", outcome="SUCCESS",
                    target_owner_module="handover", target_object_type="HND-01",
                    target_object_id=handover_analysis_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, handover_analysis_id, 201),
                )
                view = self._repository.initial_view(
                    tx, handover_analysis_id=handover_analysis_id,
                    project_id=command.project_id, actor_id=actor_id,
                )
                if not self._matches(view, command):
                    raise HandoverAnalysisCreateError("HANDOVER_UNAVAILABLE")
                tx.commit()
                return view
        except HandoverAnalysisCreateError:
            raise
        except HandoverSourceValidationError as error:
            raise HandoverAnalysisCreateError(str(error)) from None
        except ProjectAuthorizationError as error:
            raise HandoverAnalysisCreateError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverAnalysisCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise HandoverAnalysisCreateError(error.code) from None
        except Exception:
            raise HandoverAnalysisCreateError("HANDOVER_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: CreateHandoverAnalysis) -> None:
        if (type(command) is not CreateHandoverAnalysis
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.analysis_purpose) is not str
                or not 1 <= len(command.analysis_purpose) <= 255
                or command.analysis_purpose != command.analysis_purpose.strip()
                or type(command.source_documents) is not tuple
                or not 1 <= len(command.source_documents) <= 500
                or any(type(item) is not HandoverDocumentRef
                       for item in command.source_documents)
                or len({item.document_id for item in command.source_documents})
                   != len(command.source_documents)
                or len({item.document_version_id for item in command.source_documents})
                   != len(command.source_documents)):
            raise HandoverAnalysisCreateError("VALIDATION_FAILED")

    def _actor(self, tx: object, command: CreateHandoverAnalysis) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise HandoverAnalysisCreateError("HANDOVER_UNAVAILABLE")
        actor_id = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise HandoverAnalysisCreateError("AUTH_ACCESS_DENIED")
        return actor_id

    @staticmethod
    def _matches(
        view: HandoverAnalysisInitialView | None,
        command: CreateHandoverAnalysis,
    ) -> bool:
        from ..domain.source_set import canonical_handover_source_set_ref
        try:
            expected_source = canonical_handover_source_set_ref(tuple(
                item.document_version_id for item in command.source_documents
            ))
        except ValueError:
            return False
        return (type(view) is HandoverAnalysisInitialView
                and view.project_id == command.project_id
                and view.analysis_purpose == command.analysis_purpose
                and view.source_set_ref == expected_source)
