"""Atomic, immutable DRAFT Capability BaselineVersion creation."""

from __future__ import annotations

import hmac
import re
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
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .source_validation import (
    CapabilityDocumentRef, CapabilitySourceValidationError,
    CapabilitySourceValidator,
)


_CODE = re.compile(r"[A-Z][A-Z0-9_.-]{0,63}\Z", re.ASCII)
_STATES = {"AVAILABLE", "DEPRECATED", "WITHDRAWN"}


class CapabilityVersionCreateError(RuntimeError):
    def __init__(self, code: str = "CAPABILITY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CapabilityItemDraft:
    capability_item_id: uuid.UUID
    capability_code: str
    domain_name: str
    module_name: str
    feature_name: str
    name: str
    description: str
    boundary_text: str
    prerequisites: tuple[str, ...]
    interface_refs: tuple[str, ...]
    item_state: str
    document_refs: tuple[CapabilityDocumentRef, ...]
    evidence_refs: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class CreateCapabilityVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    expected_lock_version: int
    items: tuple[CapabilityItemDraft, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CapabilityBaselineLock:
    baseline_id: uuid.UUID
    baseline_state: str
    source_collection_ref: str
    lock_version: int
    highest_version_no: int
    latest_version_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class CreatedCapabilityVersion:
    baseline_version_id: uuid.UUID
    baseline_id: uuid.UUID
    version_no: int
    version_state: str
    source_collection_ref: str
    content_fingerprint: bytes = field(repr=False)
    supersedes_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    expected_lock_version: int
    lock_version: int

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (
                self.baseline_version_id, self.baseline_id, self.created_by))
                or self.version_no < 1 or self.version_state != "DRAFT"
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or self.lock_version != self.expected_lock_version + 1
                or type(self.created_at) is not datetime
                or self.created_at.tzinfo is None):
            raise CapabilityVersionCreateError()


class CapabilityVersionAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class CapabilityVersionLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityEvidencePort(Protocol):
    def get_for_trace(self, transaction: object, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> LockedEvidenceSource | None: ...


class CapabilityVersionRepositoryPort(Protocol):
    def lock_baseline(self, transaction: object, *,
                      baseline_id: uuid.UUID) -> CapabilityBaselineLock | None: ...
    def create(self, transaction: object, *, baseline: CapabilityBaselineLock,
               baseline_version_id: uuid.UUID, items: tuple[CapabilityItemDraft, ...],
               content_fingerprint: bytes,
               actor_id: uuid.UUID) -> CreatedCapabilityVersion: ...
    def initial_view(self, transaction: object, *, baseline_version_id: uuid.UUID,
                     baseline_id: uuid.UUID, actor_id: uuid.UUID,
                     expected_lock_version: int) -> CreatedCapabilityVersion | None: ...


class CapabilityVersionReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CapabilityVersionCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: CapabilityVersionAccessPort,
                 license_guard: CapabilityVersionLicensePort,
                 sources: CapabilitySourceValidator,
                 evidence: CapabilityEvidencePort,
                 repository: CapabilityVersionRepositoryPort,
                 receipts: CapabilityVersionReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (
                unit_of_work, access, license_guard, sources,
                evidence, repository, receipts, audit)):
            raise ValueError("CapabilityVersion dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._sources, self._evidence, self._repo = sources, evidence, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateCapabilityVersion) -> CreatedCapabilityVersion:
        payload = self._validate_and_payload(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            content_fingerprint = canonical_payload_fingerprint({
                "baseline_id": payload["baseline_id"],
                "items": payload["items"],
            })
            request_fingerprint = canonical_payload_fingerprint({
                "content_fingerprint": content_fingerprint.hex(),
                "expected_lock_version": payload["expected_lock_version"],
            })
            version_id = uuid.UUID(new_uuid7())
        except (IdempotencyError, ValueError):
            raise CapabilityVersionCreateError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation="V1_CAP_VERSION_CREATE", key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != "V1_CAP_VERSION" or replay.status_code != 201:
                        raise CapabilityVersionCreateError()
                    result = self._repo.initial_view(
                        tx, baseline_version_id=replay.ref_id,
                        baseline_id=command.baseline_id, actor_id=actor,
                        expected_lock_version=command.expected_lock_version,
                    )
                    if (type(result) is not CreatedCapabilityVersion
                            or not hmac.compare_digest(
                                result.content_fingerprint, content_fingerprint)):
                        raise CapabilityVersionCreateError()
                    return result
                baseline = self._repo.lock_baseline(
                    tx, baseline_id=command.baseline_id,
                )
                if type(baseline) is not CapabilityBaselineLock:
                    raise CapabilityVersionCreateError("CAPABILITY_NOT_FOUND")
                if baseline.baseline_state != "ACTIVE":
                    raise CapabilityVersionCreateError("CAPABILITY_STATE_CONFLICT")
                if baseline.lock_version != command.expected_lock_version:
                    raise CapabilityVersionCreateError("CONFLICT_VERSION")
                validated = self._sources.validate(
                    tx, self._unique_documents(command.items),
                )
                if not hmac.compare_digest(
                        validated.source_collection_ref,
                        baseline.source_collection_ref):
                    raise CapabilityVersionCreateError("CAPABILITY_SOURCE_CONFLICT")
                self._validate_evidence(tx, command.items)
                result = self._repo.create(
                    tx, baseline=baseline, baseline_version_id=version_id,
                    items=command.items, content_fingerprint=content_fingerprint,
                    actor_id=actor,
                )
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="CAP_VERSION_CREATED", outcome="SUCCESS",
                    target_owner_module="capability", target_object_type="CAP-02",
                    target_object_id=version_id, target_version_id=version_id,
                    after_state="DRAFT",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise CapabilityVersionCreateError()
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_CAP_VERSION", version_id, 201),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except CapabilityVersionCreateError:
            raise
        except CapabilitySourceValidationError:
            raise CapabilityVersionCreateError("CAPABILITY_SOURCE_UNAVAILABLE") from None
        except RuntimeLicenseError:
            raise CapabilityVersionCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise CapabilityVersionCreateError(error.code) from None
        except Exception:
            raise CapabilityVersionCreateError() from None

    @staticmethod
    def _validate_and_payload(command: CreateCapabilityVersion) -> dict[str, object]:
        if (type(command) is not CreateCapabilityVersion
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.baseline_id) is not uuid.UUID or command.baseline_id.int == 0
                or type(command.expected_lock_version) is not int
                or not 0 <= command.expected_lock_version <= 9223372036854775806
                or type(command.items) is not tuple
                or not 1 <= len(command.items) <= 500
                or any(type(item) is not CapabilityItemDraft for item in command.items)):
            raise CapabilityVersionCreateError("VALIDATION_FAILED")
        stable_ids: set[uuid.UUID] = set()
        codes: set[str] = set()
        payload_items: list[dict[str, object]] = []
        for item in command.items:
            text_fields = (item.domain_name, item.module_name, item.feature_name, item.name)
            long_fields = (item.description, item.boundary_text)
            if (type(item.capability_item_id) is not uuid.UUID
                    or item.capability_item_id.int == 0
                    or item.capability_item_id in stable_ids
                    or type(item.capability_code) is not str
                    or not _CODE.fullmatch(item.capability_code)
                    or item.capability_code in codes
                    or any(type(value) is not str or not 1 <= len(value) <= 255
                           or value != value.strip() for value in text_fields)
                    or any(type(value) is not str or not 1 <= len(value) <= 2000
                           or value != value.strip() for value in long_fields)
                    or item.item_state not in _STATES
                    or not CapabilityVersionCreateService._valid_strings(item.prerequisites)
                    or not CapabilityVersionCreateService._valid_strings(item.interface_refs)
                    or type(item.document_refs) is not tuple
                    or not 1 <= len(item.document_refs) <= 100
                    or any(type(ref) is not CapabilityDocumentRef for ref in item.document_refs)
                    or len({ref.document_id for ref in item.document_refs})
                       != len(item.document_refs)
                    or len({ref.document_version_id for ref in item.document_refs})
                       != len(item.document_refs)
                    or type(item.evidence_refs) is not tuple
                    or not 1 <= len(item.evidence_refs) <= 200
                    or any(type(ref) is not uuid.UUID or ref.int == 0
                           for ref in item.evidence_refs)
                    or len(set(item.evidence_refs)) != len(item.evidence_refs)):
                raise CapabilityVersionCreateError("VALIDATION_FAILED")
            stable_ids.add(item.capability_item_id)
            codes.add(item.capability_code)
            payload_items.append({
                "capability_item_id": str(item.capability_item_id),
                "capability_code": item.capability_code,
                "domain_name": item.domain_name, "module_name": item.module_name,
                "feature_name": item.feature_name, "name": item.name,
                "description": item.description, "boundary_text": item.boundary_text,
                "prerequisites": list(item.prerequisites),
                "interface_refs": list(item.interface_refs),
                "item_state": item.item_state,
                "document_refs": [{
                    "document_id": str(ref.document_id),
                    "document_version_id": str(ref.document_version_id),
                } for ref in item.document_refs],
                "evidence_refs": [str(ref) for ref in item.evidence_refs],
            })
        return {
            "baseline_id": str(command.baseline_id),
            "expected_lock_version": command.expected_lock_version,
            "items": payload_items,
        }

    @staticmethod
    def _valid_strings(values: object) -> bool:
        return (type(values) is tuple and len(values) <= 100
                and len(set(values)) == len(values)
                and all(type(value) is str and 1 <= len(value) <= 255
                        and value == value.strip() for value in values))

    @staticmethod
    def _unique_documents(
        items: tuple[CapabilityItemDraft, ...],
    ) -> tuple[CapabilityDocumentRef, ...]:
        found: dict[uuid.UUID, CapabilityDocumentRef] = {}
        by_document: dict[uuid.UUID, uuid.UUID] = {}
        for item in items:
            for reference in item.document_refs:
                previous = found.setdefault(reference.document_version_id, reference)
                if previous.document_id != reference.document_id:
                    raise CapabilityVersionCreateError("CAPABILITY_SOURCE_CONFLICT")
                previous_version = by_document.setdefault(
                    reference.document_id, reference.document_version_id,
                )
                if previous_version != reference.document_version_id:
                    raise CapabilityVersionCreateError("CAPABILITY_SOURCE_CONFLICT")
        return tuple(sorted(found.values(), key=lambda value: str(value.document_version_id)))

    def _validate_evidence(
        self, tx: object, items: tuple[CapabilityItemDraft, ...],
    ) -> None:
        for item in items:
            pairs = {(ref.document_id, ref.document_version_id)
                     for ref in item.document_refs}
            for evidence_id in item.evidence_refs:
                source = self._evidence.get_for_trace(
                    tx, scope="GLOBAL", project_id=None, evidence_id=evidence_id,
                )
                if (type(source) is not LockedEvidenceSource
                        or source.evidence_id != evidence_id
                        or source.scope != "GLOBAL" or source.project_id is not None
                        or (source.document_id, source.document_version_id) not in pairs
                        or type(source.content_fingerprint) is not bytes
                        or len(source.content_fingerprint) != 32
                        or type(source.lock_version) is not int
                        or source.lock_version < 0):
                    raise CapabilityVersionCreateError("CAPABILITY_EVIDENCE_UNAVAILABLE")

    def _require_admin(self, tx: object,
                       command: CreateCapabilityVersion) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise CapabilityVersionCreateError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise CapabilityVersionCreateError("AUTH_ACCESS_DENIED")
        return actor
