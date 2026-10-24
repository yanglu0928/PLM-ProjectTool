"""DeploymentAdmin-only idempotent CapabilityBaseline identity creation."""

from __future__ import annotations

import re
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

from ..domain.source_collection import canonical_source_collection_ref
from .source_validation import (
    CapabilityDocumentRef,
    CapabilitySourceValidationError,
    CapabilitySourceValidator,
)


_CODE = re.compile(r"[A-Z][A-Z0-9_.-]{0,63}\Z", re.ASCII)


class CapabilityBaselineCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateCapabilityBaseline:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_code: str
    name: str
    description: str | None
    source_documents: tuple[CapabilityDocumentRef, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CapabilityBaselineInitialView:
    baseline_id: uuid.UUID
    baseline_code: str
    name: str
    description: str | None
    source_collection_ref: str
    created_at: datetime
    baseline_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (type(self.baseline_id) is not uuid.UUID or self.baseline_id.int == 0
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None
                or self.baseline_state != "ACTIVE"
                or self.current_approved_version_ref is not None
                or self.etag != '"v0"'):
            raise ValueError("invalid initial CapabilityBaseline view")


class CapabilityBaselineAccessPort(Protocol):
    def authorized_admin(
        self, transaction: object, *, session_token: bytes,
        csrf_token: bytes, now: datetime,
    ) -> uuid.UUID | None: ...


class CapabilityBaselineLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityBaselineRepositoryPort(Protocol):
    def create(
        self, transaction: object, *, baseline_id: uuid.UUID,
        baseline_code: str, name: str, description: str | None,
        source_collection_ref: str, actor_id: uuid.UUID,
    ) -> None: ...

    def initial_view(
        self, transaction: object, *, baseline_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> CapabilityBaselineInitialView | None: ...


class CapabilityBaselineReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class CapabilityBaselineCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object],
        access: CapabilityBaselineAccessPort,
        license_guard: CapabilityBaselineLicensePort,
        sources: CapabilitySourceValidator,
        repository: CapabilityBaselineRepositoryPort,
        receipts: CapabilityBaselineReceiptPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, sources,
                repository, receipts, audit)):
            raise ValueError("CapabilityBaseline dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._sources, self._repo = sources, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateCapabilityBaseline) -> CapabilityBaselineInitialView:
        self._validate(command)
        ordered = tuple(sorted(
            command.source_documents,
            key=lambda item: str(item.document_version_id),
        ))
        try:
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "baseline_code": command.baseline_code,
                "name": command.name,
                "description": command.description,
                "source_documents": [{
                    "document_id": str(item.document_id),
                    "document_version_id": str(item.document_version_id),
                } for item in ordered],
            })
            baseline_id = uuid.UUID(new_uuid7())
        except (IdempotencyError, ValueError):
            raise CapabilityBaselineCreateError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor_id = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor_id, project_id=None,
                    operation="V1_CAP_BASELINE_CREATE",
                    key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if (replay.ref_type != "V1_CAP_BASELINE"
                            or replay.status_code != 201):
                        raise CapabilityBaselineCreateError("CAPABILITY_UNAVAILABLE")
                    view = self._repo.initial_view(
                        tx, baseline_id=replay.ref_id, actor_id=actor_id,
                    )
                    if not self._matches(view, command):
                        raise CapabilityBaselineCreateError("CAPABILITY_UNAVAILABLE")
                    return view
                validated = self._sources.validate(tx, ordered)
                self._repo.create(
                    tx, baseline_id=baseline_id,
                    baseline_code=command.baseline_code, name=command.name,
                    description=command.description,
                    source_collection_ref=validated.source_collection_ref,
                    actor_id=actor_id,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="CAP_BASELINE_CREATED", outcome="SUCCESS",
                    target_owner_module="capability", target_object_type="CAP-01",
                    target_object_id=baseline_id, after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_CAP_BASELINE", baseline_id, 201),
                )
                view = self._repo.initial_view(
                    tx, baseline_id=baseline_id, actor_id=actor_id,
                )
                if not self._matches(view, command):
                    raise CapabilityBaselineCreateError("CAPABILITY_UNAVAILABLE")
                tx.commit()
                return view
        except CapabilityBaselineCreateError:
            raise
        except CapabilitySourceValidationError as error:
            raise CapabilityBaselineCreateError(str(error)) from None
        except RuntimeLicenseError:
            raise CapabilityBaselineCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise CapabilityBaselineCreateError(error.code) from None
        except Exception:
            raise CapabilityBaselineCreateError("CAPABILITY_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: CreateCapabilityBaseline) -> None:
        if (type(command) is not CreateCapabilityBaseline
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or command.trace_id.int == 0
                or type(command.baseline_code) is not str
                or not _CODE.fullmatch(command.baseline_code)
                or type(command.name) is not str
                or not 1 <= len(command.name) <= 255
                or command.name != command.name.strip()
                or command.description is not None and (
                    type(command.description) is not str
                    or not 1 <= len(command.description) <= 2000
                    or command.description != command.description.strip())
                or type(command.source_documents) is not tuple
                or not 1 <= len(command.source_documents) <= 500
                or any(type(item) is not CapabilityDocumentRef
                       for item in command.source_documents)
                or len({item.document_id for item in command.source_documents})
                   != len(command.source_documents)
                or len({item.document_version_id for item in command.source_documents})
                   != len(command.source_documents)):
            raise CapabilityBaselineCreateError("VALIDATION_FAILED")

    def _require_admin(
        self, tx: object, command: CreateCapabilityBaseline,
    ) -> uuid.UUID:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise CapabilityBaselineCreateError("CAPABILITY_UNAVAILABLE")
        actor_id = self._access.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise CapabilityBaselineCreateError("AUTH_ACCESS_DENIED")
        return actor_id

    @staticmethod
    def _matches(
        view: CapabilityBaselineInitialView | None,
        command: CreateCapabilityBaseline,
    ) -> bool:
        try:
            expected_source = canonical_source_collection_ref(tuple(
                item.document_version_id for item in command.source_documents
            ))
        except ValueError:
            return False
        return (type(view) is CapabilityBaselineInitialView
                and view.baseline_code == command.baseline_code
                and view.name == command.name
                and view.description == command.description
                and view.source_collection_ref == expected_source)
