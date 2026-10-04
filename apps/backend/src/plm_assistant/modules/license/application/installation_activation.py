"""Internal activation after a fresh, complete License verification."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.installation_import import LicenseImportAccessPort
from plm_assistant.modules.license.application.validation_recording import (
    ValidationRecordingService, ValidationRecordingError,
)


class LicenseActivationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ActivateLicense:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    installation_id: uuid.UUID
    expected_lock_version: int
    expected_time_version: int
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ActivatedLicense:
    installation_id: uuid.UUID
    superseded_installation_id: uuid.UUID | None
    validation_event_id: uuid.UUID
    state_version: int


class ActivationRepositoryPort(Protocol):
    def activate(self, transaction: object, *, installation_id: uuid.UUID,
                 expected_lock_version: int, event_id: uuid.UUID,
                 trace_id: uuid.UUID, now: datetime) -> ActivatedLicense | None: ...


class LicenseActivationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: LicenseImportAccessPort, recorder: ValidationRecordingService,
                 repository: ActivationRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, recorder, repository, audit)):
            raise ValueError("license activation dependencies are required")
        self._unit_of_work = unit_of_work
        self._access = access
        self._recorder = recorder
        self._repository = repository
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def activate_imported(self, command: ActivateLicense) -> ActivatedLicense:
        if (type(command) is not ActivateLicense
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.installation_id) is not uuid.UUID or command.installation_id.int == 0
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.expected_lock_version) is not int or command.expected_lock_version < 0
                or type(command.expected_time_version) is not int or command.expected_time_version < 0):
            raise LicenseActivationError("VALIDATION_FAILED")
        with self._unit_of_work() as tx:
            if self._authorized_actor(tx, command) is None:
                raise LicenseActivationError("AUTH_ACCESS_DENIED")
        try:
            recorded = self._recorder.record_imported(
                command.installation_id, expected_lock_version=command.expected_lock_version,
                expected_time_version=command.expected_time_version, trace_id=command.trace_id,
            )
        except ValidationRecordingError as exc:
            raise LicenseActivationError(exc.code) from None
        if recorded.code != "VALID":
            raise LicenseActivationError(recorded.code)
        if (recorded.installation_id != command.installation_id
                or recorded.lock_version != command.expected_lock_version + 1):
            raise LicenseActivationError("TRUST_STATE_INVALID")
        with self._unit_of_work() as tx:
            actor_id = self._authorized_actor(tx, command)
            if actor_id is None:
                raise LicenseActivationError("AUTH_ACCESS_DENIED")
            result = self._repository.activate(
                tx, installation_id=command.installation_id,
                expected_lock_version=recorded.lock_version,
                event_id=recorded.event_id, trace_id=command.trace_id,
                now=self._now(),
            )
            if result is None:
                raise LicenseActivationError("INSTALLATION_CONFLICT")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                actor_type="USER", actor_id=actor_id, original_actor_id=None,
                actor_hint_digest=None, action="LICENSE_ACTIVATED", outcome="SUCCESS",
                target_owner_module="license", target_object_type="LIC-01",
                target_object_id=result.installation_id, target_version_id=None,
                before_state="IMPORTED", after_state="ACTIVE",
            ))
            tx.commit()
            return result

    def _authorized_actor(self, tx: object, command: ActivateLicense) -> uuid.UUID | None:
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=self._now(),
        )
        return actor if type(actor) is uuid.UUID and actor.int != 0 else None

    def _now(self) -> datetime:
        try:
            now = self._clock()
        except Exception:
            raise LicenseActivationError("TRUST_STATE_INVALID") from None
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise LicenseActivationError("TRUST_STATE_INVALID")
        return now.astimezone(timezone.utc)
