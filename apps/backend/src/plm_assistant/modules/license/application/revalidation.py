"""Admin-controlled revalidation of the current active License."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.installation_import import LicenseImportAccessPort
from plm_assistant.modules.license.application.license_validation import (
    LicenseService, LicenseValidationError, VerifiedFullBundleLicense,
)


class LicenseRevalidationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RevalidateLicense:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RecoverySource:
    installation_id: uuid.UUID
    public_key_ref: str
    signed_document: bytes = field(repr=False)
    document_sha256: bytes = field(repr=False)
    state_version: int = 0
    installation_lock_version: int = 0
    current_event_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class RevalidationResult:
    installation_id: uuid.UUID
    event_id: uuid.UUID
    code: str
    state_version: int


class RecoveryRepositoryPort(Protocol):
    def read_active(self, transaction: object) -> RecoverySource | None: ...
    def record(self, transaction: object, *, source: RecoverySource, code: str,
               verified: VerifiedFullBundleLicense | None, now: datetime,
               trace_id: uuid.UUID) -> RevalidationResult | None: ...


class TrustedTimeVersionPort(Protocol):
    def current_verified_version(self) -> int: ...


class LicenseRevalidationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: LicenseImportAccessPort,
                 repository: RecoveryRepositoryPort, validator: LicenseService,
                 trusted_time: TrustedTimeVersionPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, repository, validator, trusted_time, audit)):
            raise ValueError("license recovery dependencies are required")
        self._unit_of_work, self._access, self._repository = unit_of_work, access, repository
        self._validator, self._trusted_time, self._audit = validator, trusted_time, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revalidate_active(self, command: RevalidateLicense) -> RevalidationResult:
        if (type(command) is not RevalidateLicense
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise LicenseRevalidationError("VALIDATION_FAILED")
        now = self._now()
        try:
            with self._unit_of_work() as tx:
                actor = self._access.authorized_admin(
                    tx, session_token=command.session_token, csrf_token=command.csrf_token, now=now,
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise LicenseRevalidationError("AUTH_ACCESS_DENIED")
                source = self._repository.read_active(tx)
                if source is None:
                    raise LicenseRevalidationError("NOT_INSTALLED")
                if (type(source.signed_document) is not bytes
                        or not 1 <= len(source.signed_document) <= 65536
                        or type(source.document_sha256) is not bytes
                        or len(source.document_sha256) != 32
                        or not hmac.compare_digest(hashlib.sha256(source.signed_document).digest(),
                                                   source.document_sha256)):
                    raise LicenseRevalidationError("TRUST_STATE_INVALID")
                verified = None
                try:
                    expected_version = self._trusted_time.current_verified_version()
                    verified = self._validator.validate(
                        source.signed_document, expected_time_version=expected_version,
                        trace_id=command.trace_id, expected_public_key_ref=source.public_key_ref,
                    )
                    code = ("VALID" if hmac.compare_digest(verified.document_sha256,
                                                           source.document_sha256)
                            else "TRUST_STATE_INVALID")
                    if code != "VALID":
                        verified = None
                except LicenseValidationError as exc:
                    code = exc.code
                except Exception:
                    code = "TRUST_STATE_INVALID"
                result = self._repository.record(
                    tx, source=source, code=code, verified=verified, now=now,
                    trace_id=command.trace_id,
                )
                if result is None:
                    raise LicenseRevalidationError("TRUST_STATE_INVALID")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                    actor_type="USER", actor_id=actor, original_actor_id=None,
                    actor_hint_digest=None, action="LICENSE_REVALIDATED",
                    outcome="SUCCESS" if code == "VALID" else "DENIED",
                    target_owner_module="license", target_object_type="LIC-01",
                    target_object_id=source.installation_id, reason_code=code,
                ))
                tx.commit()
            if code != "VALID":
                raise LicenseRevalidationError(code)
            return result
        except LicenseRevalidationError:
            raise
        except Exception:
            raise LicenseRevalidationError("TRUST_STATE_INVALID") from None

    def _now(self) -> datetime:
        try:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("timezone required")
            return now.astimezone(timezone.utc)
        except Exception:
            raise LicenseRevalidationError("TRUST_STATE_INVALID") from None
