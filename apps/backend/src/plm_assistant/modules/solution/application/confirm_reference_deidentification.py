"""Explicit DeploymentAdmin attestation over freshly proven GLOBAL sources."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceError, ReferenceSourceRequest,
)


_STATEMENT = "I_VERIFIED_DEIDENTIFICATION"
_MAX_VALIDITY = timedelta(days=30)
_OPERATION = "V1_SOL_REFERENCE_DEIDENTIFICATION_CONFIRM"
_RESULT_TYPE = "V1_SOL_REFERENCE_DEIDENTIFICATION"


class ReferenceDeidentificationConfirmError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ConfirmReferenceDeidentification:
    sources: ReferenceSourceRequest = field(repr=False)
    csrf_token: bytes = field(repr=False)
    expires_at: datetime
    attestation_statement: str
    idempotency_key: str = field(repr=False)
    expected_source_fingerprint: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ReferenceDeidentificationConfirmationView:
    confirmation_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    confirmed_by: uuid.UUID
    confirmed_at: datetime
    expires_at: datetime
    trace_id: uuid.UUID


class AdminAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class SourceProofPort(Protocol):
    def prove_sources(self, transaction: object,
                      request: ReferenceSourceRequest) -> ProvenReferenceSources: ...


class ConfirmationRepositoryPort(Protocol):
    def create(self, transaction: object, *, confirmation_id: uuid.UUID,
               proven: ProvenReferenceSources, request: ReferenceSourceRequest,
               actor_id: uuid.UUID, confirmed_at: datetime, expires_at: datetime) -> None: ...

    def view(self, transaction: object, *, confirmation_id: uuid.UUID,
             actor_id: uuid.UUID) -> ReferenceDeidentificationConfirmationView | None: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...

    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class ReferenceDeidentificationConfirmService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AdminAccessPort,
                 license_guard: LicensePort, sources: SourceProofPort,
                 repository: ConfirmationRepositoryPort, receipts: ReceiptPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(part is None for part in (
                unit_of_work, access, license_guard, sources, repository, receipts, audit)):
            raise ValueError("Reference confirmation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._sources, self._repo, self._receipts = sources, repository, receipts
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def confirm(self, command: ConfirmReferenceDeidentification,
                ) -> ReferenceDeidentificationConfirmationView:
        self._validate(command)
        request = command.sources
        try:
            validate_idempotency_key(command.idempotency_key)
            confirmation_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=request.trace_id)
            with self._uow() as tx:
                now, actor = self._require_admin(tx, command)
                if not now < command.expires_at <= now + _MAX_VALIDITY:
                    raise ReferenceDeidentificationConfirmError("VALIDATION_FAILED")
                proven = self._sources.prove_sources(tx, request)
                if (type(proven) is not ProvenReferenceSources
                        or proven.scope != "GLOBAL" or proven.project_id is not None
                        or len(proven.document_versions) != len(request.document_version_ids)
                        or len(proven.evidence) != len(request.evidence_ids)
                        or type(proven.content_fingerprint) is not bytes
                        or len(proven.content_fingerprint) != 32):
                    raise ReferenceDeidentificationConfirmError()
                if (command.expected_source_fingerprint is not None
                        and not hmac.compare_digest(
                            proven.content_fingerprint,
                            command.expected_source_fingerprint)):
                    raise ReferenceDeidentificationConfirmError("SOURCE_SNAPSHOT_CHANGED")
                fingerprint = canonical_payload_fingerprint({
                    "source_fingerprint": proven.content_fingerprint.hex(),
                    "source_project_class": request.source_project_class,
                    "deidentification_class": request.deidentification_class,
                    "applicability": request.applicability,
                    "expires_at": command.expires_at.isoformat(),
                    "statement": command.attestation_statement,
                })
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation=_OPERATION,
                    key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type != _RESULT_TYPE or replay.status_code != 201:
                        raise ReferenceDeidentificationConfirmError()
                    view = self._repo.view(tx, confirmation_id=replay.ref_id, actor_id=actor)
                    if not self._matches(view, proven, command, actor, now):
                        raise ReferenceDeidentificationConfirmError()
                    return view
                self._repo.create(
                    tx, confirmation_id=confirmation_id, proven=proven,
                    request=request, actor_id=actor, confirmed_at=now,
                    expires_at=command.expires_at,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=request.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="SOL_REFERENCE_DEIDENTIFICATION_CONFIRMED",
                    outcome="SUCCESS", target_owner_module="solution",
                    target_object_type="SOL-01", target_object_id=confirmation_id,
                    after_state="CONFIRMED",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _RESULT_TYPE, confirmation_id, 201))
                view = self._repo.view(tx, confirmation_id=confirmation_id, actor_id=actor)
                if not self._matches(view, proven, command, actor, now):
                    raise ReferenceDeidentificationConfirmError()
                tx.commit()
                return view
        except ReferenceDeidentificationConfirmError:
            raise
        except ReferenceSourceError as error:
            raise ReferenceDeidentificationConfirmError(error.code) from None
        except RuntimeLicenseError:
            raise ReferenceDeidentificationConfirmError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise ReferenceDeidentificationConfirmError(error.code) from None
        except Exception:
            raise ReferenceDeidentificationConfirmError() from None

    @staticmethod
    def _validate(command: ConfirmReferenceDeidentification) -> None:
        if (type(command) is not ConfirmReferenceDeidentification
                or type(command.sources) is not ReferenceSourceRequest
                or command.sources.scope != "GLOBAL"
                or command.sources.project_id is not None
                or type(command.sources.session_token) is not bytes
                or len(command.sources.session_token) != 32
                or type(command.sources.trace_id) is not uuid.UUID
                or command.sources.trace_id.int == 0
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.expires_at) is not datetime
                or command.expires_at.tzinfo is None
                or command.expires_at.utcoffset() is None
                or command.attestation_statement != _STATEMENT
                or (command.expected_source_fingerprint is not None
                    and (type(command.expected_source_fingerprint) is not bytes
                         or len(command.expected_source_fingerprint) != 32))):
            raise ReferenceDeidentificationConfirmError("VALIDATION_FAILED")

    def _require_admin(self, tx: object, command: ConfirmReferenceDeidentification,
                       ) -> tuple[datetime, uuid.UUID]:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceDeidentificationConfirmError()
        now = now.astimezone(timezone.utc)
        actor = self._access.authorized_admin(
            tx, session_token=command.sources.session_token,
            csrf_token=command.csrf_token, now=now)
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ReferenceDeidentificationConfirmError("AUTH_ACCESS_DENIED")
        return now, actor

    @staticmethod
    def _matches(view: ReferenceDeidentificationConfirmationView | None,
                 proven: ProvenReferenceSources,
                 command: ConfirmReferenceDeidentification,
                 actor_id: uuid.UUID, now: datetime) -> bool:
        return (type(view) is ReferenceDeidentificationConfirmationView
                and type(view.confirmation_id) is uuid.UUID
                and view.confirmation_id.int != 0
                and view.source_fingerprint == proven.content_fingerprint
                and view.expires_at == command.expires_at
                and type(view.expires_at) is datetime
                and view.expires_at.tzinfo is not None
                and now < view.expires_at
                and view.confirmed_by == actor_id
                and type(view.trace_id) is uuid.UUID and view.trace_id.int != 0
                and type(view.confirmed_at) is datetime
                and view.confirmed_at.tzinfo is not None
                and view.confirmed_at <= now)
