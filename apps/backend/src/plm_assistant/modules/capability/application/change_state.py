"""DeploymentAdmin Capability metadata, archive and restriction owners."""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)

from .read_capability import CapabilityBaselineView, CapabilityVersionView


_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)


class CapabilityStateError(RuntimeError):
    def __init__(self, code: str = "CAPABILITY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchCapabilityBaseline:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    expected_lock_version: int
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class ArchiveCapabilityBaseline:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RestrictCapabilityVersion:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    baseline_id: uuid.UUID
    baseline_version_id: uuid.UUID
    reason_code: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RestrictedCapabilityVersion:
    version: CapabilityVersionView
    reason_code: str


@dataclass(frozen=True, slots=True)
class CapabilityRestrictionMutation:
    version: CapabilityVersionView
    before_state: str


class CapabilityStateAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class CapabilityStateLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class CapabilityStateRepositoryPort(Protocol):
    def get_baseline(self, transaction: object, *,
                     baseline_id: uuid.UUID) -> CapabilityBaselineView | None: ...
    def patch(self, transaction: object, *, baseline_id: uuid.UUID,
              expected_lock_version: int, name: str, description: str | None,
              actor_id: uuid.UUID) -> CapabilityBaselineView: ...
    def archive(self, transaction: object, *, baseline_id: uuid.UUID,
                expected_lock_version: int,
                actor_id: uuid.UUID) -> CapabilityBaselineView: ...
    def get_version(self, transaction: object, *, baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> CapabilityVersionView | None: ...
    def restrict(self, transaction: object, *, baseline_id: uuid.UUID,
                 baseline_version_id: uuid.UUID,
                 actor_id: uuid.UUID) -> CapabilityRestrictionMutation: ...


class CapabilityStateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CapabilityStateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: CapabilityStateAccessPort,
                 license_guard: CapabilityStateLicensePort,
                 repository: CapabilityStateRepositoryPort,
                 receipts: CapabilityStateReceiptPort,
                 audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, repository, receipts, audit)):
            raise ValueError("Capability state dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchCapabilityBaseline) -> CapabilityBaselineView:
        self._validate_common(command, PatchCapabilityBaseline)
        name = self._text(command.name, 255, nullable=False)
        description = self._text(command.description, 2000, nullable=True)
        return self._execute(command, lambda tx, actor: self._patch(
            tx, actor, command, name, description,
        ))

    def archive(self, command: ArchiveCapabilityBaseline) -> CapabilityBaselineView:
        self._validate_common(command, ArchiveCapabilityBaseline)
        try:
            validate_idempotency_key(command.idempotency_key)
        except IdempotencyError:
            raise CapabilityStateError("VALIDATION_FAILED") from None
        fingerprint = canonical_payload_fingerprint({
            "baseline_id": str(command.baseline_id),
            "expected_lock_version": command.expected_lock_version,
        })
        return self._execute(command, lambda tx, actor: self._archive(
            tx, actor, command, fingerprint,
        ))

    def restrict(self, command: RestrictCapabilityVersion) -> RestrictedCapabilityVersion:
        self._validate_common(command, RestrictCapabilityVersion)
        if (type(command.baseline_version_id) is not uuid.UUID
                or command.baseline_version_id.int == 0
                or type(command.reason_code) is not str
                or _REASON.fullmatch(command.reason_code) is None):
            raise CapabilityStateError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
        except IdempotencyError:
            raise CapabilityStateError("VALIDATION_FAILED") from None
        fingerprint = canonical_payload_fingerprint({
            "baseline_id": str(command.baseline_id),
            "baseline_version_id": str(command.baseline_version_id),
            "reason_code": command.reason_code,
        })
        return self._execute(command, lambda tx, actor: self._restrict(
            tx, actor, command, fingerprint,
        ))

    def _patch(self, tx: object, actor: uuid.UUID, command: PatchCapabilityBaseline,
               name: str, description: str | None) -> CapabilityBaselineView:
        view = self._repo.patch(
            tx, baseline_id=command.baseline_id,
            expected_lock_version=command.expected_lock_version,
            name=name, description=description, actor_id=actor,
        )
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None,
            action="CAP_BASELINE_PATCHED", outcome="SUCCESS",
            target_owner_module="capability", target_object_type="CAP-01",
            target_object_id=command.baseline_id, reason_code="METADATA_UPDATED",
            before_state="ACTIVE", after_state="ACTIVE",
        ))
        return view

    def _archive(self, tx: object, actor: uuid.UUID,
                 command: ArchiveCapabilityBaseline,
                 fingerprint: bytes) -> CapabilityBaselineView:
        scope = IdempotencyScope.from_key(
            actor_id=actor, project_id=None,
            operation="V1_CAP_BASELINE_ARCHIVE", key=command.idempotency_key,
        )
        replay = self._receipts.reserve(
            tx, scope=scope, request_fingerprint=fingerprint,
        )
        if replay is not None:
            if (replay.ref_type != "V1_CAP_BASELINE_ARCHIVE"
                    or replay.ref_id != command.baseline_id
                    or replay.status_code != 200):
                raise CapabilityStateError()
            view = self._repo.get_baseline(tx, baseline_id=command.baseline_id)
            if (type(view) is not CapabilityBaselineView
                    or view.state != "ARCHIVED"
                    or view.etag != f'"v{command.expected_lock_version + 1}"'):
                raise CapabilityStateError()
            return view
        view = self._repo.archive(
            tx, baseline_id=command.baseline_id,
            expected_lock_version=command.expected_lock_version, actor_id=actor,
        )
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None,
            action="CAP_BASELINE_ARCHIVED", outcome="SUCCESS",
            target_owner_module="capability", target_object_type="CAP-01",
            target_object_id=command.baseline_id,
            before_state="ACTIVE", after_state="ARCHIVED",
        ))
        self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
            "V1_CAP_BASELINE_ARCHIVE", command.baseline_id, 200,
        ))
        return view

    def _restrict(self, tx: object, actor: uuid.UUID,
                  command: RestrictCapabilityVersion,
                  fingerprint: bytes) -> RestrictedCapabilityVersion:
        scope = IdempotencyScope.from_key(
            actor_id=actor, project_id=None,
            operation="V1_CAP_VERSION_RESTRICT", key=command.idempotency_key,
        )
        replay = self._receipts.reserve(
            tx, scope=scope, request_fingerprint=fingerprint,
        )
        if replay is not None:
            if (replay.ref_type != "V1_CAP_VERSION_RESTRICT"
                    or replay.ref_id != command.baseline_version_id
                    or replay.status_code != 200):
                raise CapabilityStateError()
            view = self._repo.get_version(
                tx, baseline_id=command.baseline_id,
                baseline_version_id=command.baseline_version_id,
            )
            if type(view) is not CapabilityVersionView or view.state != "RESTRICTED":
                raise CapabilityStateError()
            return RestrictedCapabilityVersion(view, command.reason_code)
        mutation = self._repo.restrict(
            tx, baseline_id=command.baseline_id,
            baseline_version_id=command.baseline_version_id, actor_id=actor,
        )
        if (type(mutation) is not CapabilityRestrictionMutation
                or type(mutation.version) is not CapabilityVersionView
                or mutation.version.state != "RESTRICTED"):
            raise CapabilityStateError()
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="DEPLOYMENT",
            target_project_id=None, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None,
            action="CAP_VERSION_RESTRICTED", outcome="SUCCESS",
            target_owner_module="capability", target_object_type="CAP-02",
            target_object_id=command.baseline_version_id,
            target_version_id=command.baseline_version_id,
            reason_code=command.reason_code,
            before_state=mutation.before_state,
            after_state="RESTRICTED",
        ))
        self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
            "V1_CAP_VERSION_RESTRICT", command.baseline_version_id, 200,
        ))
        return RestrictedCapabilityVersion(mutation.version, command.reason_code)

    def _execute(self, command: object,
                 operation: Callable[[object, uuid.UUID], object]):
        try:
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)  # type: ignore[attr-defined]
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                result = operation(tx, actor)
                tx.commit()
                return result
        except CapabilityStateError:
            raise
        except RuntimeLicenseError:
            raise CapabilityStateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise CapabilityStateError(error.code) from None
        except Exception:
            raise CapabilityStateError() from None

    def _require_admin(self, tx: object, command: object) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise CapabilityStateError()
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token,  # type: ignore[attr-defined]
            csrf_token=command.csrf_token,  # type: ignore[attr-defined]
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise CapabilityStateError("AUTH_ACCESS_DENIED")
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
                or type(command.baseline_id) is not uuid.UUID  # type: ignore[attr-defined]
                or command.baseline_id.int == 0):  # type: ignore[attr-defined]
            raise CapabilityStateError("VALIDATION_FAILED")
        if command_type in (PatchCapabilityBaseline, ArchiveCapabilityBaseline) and (
                type(command.expected_lock_version) is not int  # type: ignore[attr-defined]
                or not 0 <= command.expected_lock_version <= 9223372036854775806):  # type: ignore[attr-defined]
            raise CapabilityStateError("VALIDATION_FAILED")

    @staticmethod
    def _text(value: object, maximum: int, *, nullable: bool) -> str | None:
        if value is None and nullable:
            return None
        if type(value) is not str:
            raise CapabilityStateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (not 1 <= len(result) <= maximum
                or any(unicodedata.category(char)[0] == "C" for char in result)):
            raise CapabilityStateError("VALIDATION_FAILED")
        return result
