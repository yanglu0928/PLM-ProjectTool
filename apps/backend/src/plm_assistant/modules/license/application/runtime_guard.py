"""Fail-closed internal License check for future licensed operations."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.license_validation import (
    LicenseService, LicenseValidationError, VerifiedFullBundleLicense,
)


class RuntimeLicenseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RuntimeLicenseSnapshot:
    code: str
    state_id: uuid.UUID | None = None
    state_version: int | None = None
    installation_id: uuid.UUID | None = None
    current_event_id: uuid.UUID | None = None
    public_key_ref: str | None = None
    signed_document: bytes | None = field(default=None, repr=False)
    document_sha256: bytes | None = field(default=None, repr=False)
    machine_fingerprint_hash: bytes | None = field(default=None, repr=False)
    entitlement_snapshot: dict[str, str] | None = field(default=None, repr=False)


class TrustedTimeVersionPort(Protocol):
    def current_verified_version(self) -> int: ...


class RuntimeLicenseRepositoryPort(Protocol):
    def read_current(self, transaction: object) -> RuntimeLicenseSnapshot: ...
    def record_check(self, transaction: object, *, snapshot: RuntimeLicenseSnapshot,
                     code: str, verified: VerifiedFullBundleLicense | None,
                     now: datetime, trace_id: uuid.UUID) -> bool: ...


class LicenseRuntimeGuard:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RuntimeLicenseRepositoryPort, validator: LicenseService,
                 trusted_time: TrustedTimeVersionPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, repository, validator, trusted_time, audit)):
            raise ValueError("runtime guard dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._validator = validator
        self._trusted_time = trusted_time
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def require_valid(self, *, trace_id: uuid.UUID) -> VerifiedFullBundleLicense:
        if type(trace_id) is not uuid.UUID or trace_id.int == 0:
            raise RuntimeLicenseError("TRUST_STATE_INVALID")
        now = self._now()
        try:
            with self._unit_of_work() as tx:
                snapshot = self._repository.read_current(tx)
                if snapshot.code != "VALID":
                    raise RuntimeLicenseError(snapshot.code)
                if (type(snapshot.signed_document) is not bytes
                        or type(snapshot.public_key_ref) is not str
                        or type(snapshot.document_sha256) is not bytes
                        or type(snapshot.machine_fingerprint_hash) is not bytes
                        or type(snapshot.entitlement_snapshot) is not dict):
                    raise RuntimeLicenseError("TRUST_STATE_INVALID")
                try:
                    expected_version = self._trusted_time.current_verified_version()
                except Exception:
                    self._record(tx, snapshot, "TRUST_STATE_INVALID", None, now, trace_id)
                    tx.commit()
                    raise RuntimeLicenseError("TRUST_STATE_INVALID") from None
                try:
                    verified = self._validator.validate(
                        snapshot.signed_document, expected_time_version=expected_version,
                        trace_id=trace_id, expected_public_key_ref=snapshot.public_key_ref,
                    )
                except LicenseValidationError as exc:
                    self._record(tx, snapshot, exc.code, None, now, trace_id)
                    tx.commit()
                    raise RuntimeLicenseError(exc.code) from None
                except Exception:
                    self._record(tx, snapshot, "TRUST_STATE_INVALID", None, now, trace_id)
                    tx.commit()
                    raise RuntimeLicenseError("TRUST_STATE_INVALID") from None
                expected_entitlement = {
                    "product_code": verified.product_code, "grant_scope": verified.grant_scope,
                    "valid_from": verified.valid_from.isoformat(),
                    "valid_to": verified.valid_to.isoformat(),
                }
                if (not hmac.compare_digest(verified.document_sha256, snapshot.document_sha256)
                        or not hmac.compare_digest(verified.machine_fingerprint_hash,
                                                   snapshot.machine_fingerprint_hash)
                        or expected_entitlement != snapshot.entitlement_snapshot):
                    self._record(tx, snapshot, "TRUST_STATE_INVALID", None, now, trace_id)
                    tx.commit()
                    raise RuntimeLicenseError("TRUST_STATE_INVALID")
                self._record(tx, snapshot, "VALID", verified, now, trace_id)
                tx.commit()
                return verified
        except RuntimeLicenseError:
            raise
        except Exception:
            raise RuntimeLicenseError("TRUST_STATE_INVALID") from None

    def _record(self, tx: object, snapshot: RuntimeLicenseSnapshot, code: str,
                verified: VerifiedFullBundleLicense | None, now: datetime,
                trace_id: uuid.UUID) -> None:
        if not self._repository.record_check(
            tx, snapshot=snapshot, code=code, verified=verified,
            now=now, trace_id=trace_id,
        ):
            raise RuntimeLicenseError("TRUST_STATE_INVALID") from None
        self._audit.append(tx, AuditEventDraft(
            trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
            actor_type="UNRESOLVED", actor_id=None, original_actor_id=None,
            actor_hint_digest=None, action="LICENSE_RUNTIME_CHECK",
            outcome="SUCCESS" if code == "VALID" else "DENIED",
            target_owner_module="license", target_object_type="LIC-01",
            target_object_id=snapshot.installation_id, reason_code=code,
        ))

    def _now(self) -> datetime:
        try:
            now = self._clock()
        except Exception:
            raise RuntimeLicenseError("TRUST_STATE_INVALID") from None
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeLicenseError("TRUST_STATE_INVALID")
        return now.astimezone(timezone.utc)
