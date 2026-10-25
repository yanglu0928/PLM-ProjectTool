"""Deployment-admin review of non-sensitive GLOBAL Reference candidate labels."""

from __future__ import annotations

import hmac
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

from .create_reference_solution import GlobalAccessPort, LicensePort, ReceiptPort
from .reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
)
from .set_reference_eligibility import LockedReferenceEligibility


_OPERATION = "V1_SOL_GLOBAL_REFERENCE_PUBLICATION_SET"


class GlobalReferencePublicationError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SetGlobalReferencePublication:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    reference_solution_id: uuid.UUID
    expected_reference_version_id: uuid.UUID
    expected_event_no: int
    event_kind: str
    display_label: str | None
    reason: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class LockedGlobalPublicationTarget:
    reference: LockedReferenceEligibility
    latest_eligibility_current: bool
    latest_event_no: int
    latest_event_kind: str | None
    latest_event_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class GlobalReferencePublicationResult:
    publication_event_id: uuid.UUID
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    event_no: int
    event_kind: str
    display_label: str | None
    reason: str
    created_at: datetime


class SourcePort(Protocol):
    def qualify(self, transaction: object,
                request: ReferenceSourceRequest) -> QualifiedReferenceSources: ...


class RepositoryPort(Protocol):
    def current(self, transaction: object, *, root_id: uuid.UUID
                ) -> LockedGlobalPublicationTarget | None: ...
    def append(self, transaction: object, *, current: LockedGlobalPublicationTarget,
               event_id: uuid.UUID, actor_id: uuid.UUID,
               command: SetGlobalReferencePublication
               ) -> GlobalReferencePublicationResult: ...
    def result(self, transaction: object, *, event_id: uuid.UUID,
               root_id: uuid.UUID) -> GlobalReferencePublicationResult | None: ...


def _valid_text(value: object, *, maximum: int) -> bool:
    return (type(value) is str and 1 <= len(value) <= maximum
            and value == value.strip()
            and unicodedata.is_normalized("NFC", value)
            and all(unicodedata.category(char) != "Cc" for char in value))


class GlobalReferencePublicationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 admin: GlobalAccessPort, license_guard: LicensePort,
                 sources: SourcePort, repository: RepositoryPort,
                 receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(part is None for part in (
                unit_of_work, admin, license_guard, sources, repository,
                receipts, audit)):
            raise ValueError("GLOBAL publication dependencies required")
        self._uow, self._admin_port, self._guard = unit_of_work, admin, license_guard
        self._sources, self._repo = sources, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def set(self, command: SetGlobalReferencePublication) -> GlobalReferencePublicationResult:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            with self._uow() as tx:
                self._admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation=_OPERATION,
                    key=command.idempotency_key)
                fingerprint = canonical_payload_fingerprint({
                    "reference_solution_id": str(command.reference_solution_id),
                    "expected_reference_version_id": str(command.expected_reference_version_id),
                    "expected_event_no": command.expected_event_no,
                    "event_kind": command.event_kind,
                    "display_label": command.display_label,
                    "reason": command.reason,
                })
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise GlobalReferencePublicationError()
                    original = self._repo.result(
                        tx, event_id=replay.ref_id,
                        root_id=command.reference_solution_id)
                    if (original is None
                            or original.reference_version_id
                            != command.expected_reference_version_id
                            or original.event_no != command.expected_event_no + 1
                            or original.event_kind != command.event_kind
                            or original.display_label != command.display_label
                            or original.reason != command.reason):
                        raise GlobalReferencePublicationError()
                    return original
                current = self._repo.current(
                    tx, root_id=command.reference_solution_id)
                if current is None:
                    raise GlobalReferencePublicationError("RESOURCE_NOT_FOUND")
                ref = current.reference
                if (ref.scope != "GLOBAL" or ref.project_id is not None
                        or ref.reference_solution_id != command.reference_solution_id
                        or ref.reference_version_id != command.expected_reference_version_id
                        or current.latest_event_no != command.expected_event_no):
                    raise GlobalReferencePublicationError("VERSION_CONFLICT")
                if command.event_kind == "PUBLISH":
                    if (ref.eligibility_state != "ELIGIBLE"
                            or not current.latest_eligibility_current
                            or current.latest_event_kind == "PUBLISH"
                            and current.latest_event_version_id == ref.reference_version_id):
                        raise GlobalReferencePublicationError("CONFLICT_STATE")
                    qualified = self._sources.qualify(tx, ReferenceSourceRequest(
                        session_token=command.session_token,
                        trace_id=command.trace_id, scope="GLOBAL", project_id=None,
                        document_version_ids=ref.document_version_ids,
                        evidence_ids=ref.evidence_ids,
                        source_project_class=ref.source_project_class,
                        deidentification_class=ref.deidentification_class,
                        applicability=ref.applicability))
                    if (type(qualified) is not QualifiedReferenceSources
                            or qualified.scope != "GLOBAL"
                            or qualified.project_id is not None
                            or type(qualified.content_fingerprint) is not bytes
                            or not hmac.compare_digest(
                                qualified.content_fingerprint, ref.source_fingerprint)
                            or qualified.deidentification_confirmation_id
                            != ref.deidentification_confirmation_id
                            or tuple(item.document_version_id
                                     for item in qualified.document_versions)
                            != ref.document_version_ids
                            or tuple(item.evidence_id for item in qualified.evidence)
                            != ref.evidence_ids):
                        raise GlobalReferencePublicationError("CONFLICT_STATE")
                elif (current.latest_event_kind != "PUBLISH"
                      or current.latest_event_version_id != ref.reference_version_id):
                    raise GlobalReferencePublicationError("CONFLICT_STATE")
                event_id = uuid.UUID(new_uuid7())
                result = self._repo.append(
                    tx, current=current, event_id=event_id,
                    actor_id=actor, command=command)
                if (type(result) is not GlobalReferencePublicationResult
                        or result.publication_event_id != event_id
                        or result.reference_solution_id != command.reference_solution_id
                        or result.reference_version_id != ref.reference_version_id
                        or result.event_no != current.latest_event_no + 1
                        or result.event_kind != command.event_kind
                        or result.display_label != command.display_label
                        or result.reason != command.reason):
                    raise GlobalReferencePublicationError()
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="SOL_GLOBAL_REFERENCE_PUBLICATION_SET",
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-01",
                    target_object_id=ref.reference_solution_id,
                    before_state=current.latest_event_kind or "UNPUBLISHED",
                    after_state=command.event_kind,
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, event_id, 200))
                tx.commit()
                return result
        except GlobalReferencePublicationError:
            raise
        except (IdempotencyError, ReferenceSourceError) as error:
            raise GlobalReferencePublicationError(error.code) from None
        except RuntimeLicenseError:
            raise GlobalReferencePublicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalReferencePublicationError() from None

    @staticmethod
    def _validate(command: SetGlobalReferencePublication) -> None:
        if (type(command) is not SetGlobalReferencePublication
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.reference_solution_id) is not uuid.UUID
                or command.reference_solution_id.int == 0
                or type(command.expected_reference_version_id) is not uuid.UUID
                or command.expected_reference_version_id.int == 0
                or type(command.expected_event_no) is not int
                or not 0 <= command.expected_event_no < 2**31-1
                or command.event_kind not in ("PUBLISH", "REVOKE")
                or (command.event_kind == "PUBLISH"
                    and not _valid_text(command.display_label, maximum=160))
                or (command.event_kind == "REVOKE"
                    and command.display_label is not None)
                or not _valid_text(command.reason, maximum=2000)):
            raise GlobalReferencePublicationError("VALIDATION_FAILED")

    def _admin(self, tx: object, command: SetGlobalReferencePublication) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise GlobalReferencePublicationError()
        actor = self._admin_port.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc))
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise GlobalReferencePublicationError("AUTH_ACCESS_DENIED")
        return actor
