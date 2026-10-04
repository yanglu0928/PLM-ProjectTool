"""Record a stored imported License verification attempt without activating it."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.license_validation import (
    LicenseService, LicenseValidationError, VerifiedFullBundleLicense,
)


class ValidationRecordingError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ImportedDocument:
    installation_id: uuid.UUID
    public_key_ref: str
    lock_version: int
    signed_document: bytes | None
    document_sha256: bytes | None


@dataclass(frozen=True, slots=True)
class RecordedValidation:
    installation_id: uuid.UUID
    event_id: uuid.UUID
    code: str
    lock_version: int


class ValidationRecordingRepositoryPort(Protocol):
    def read_imported(self, transaction: object, installation_id: uuid.UUID) -> ImportedDocument | None: ...
    def append_result(self, transaction: object, *, installation_id: uuid.UUID, code: str,
                      document_sha256: bytes | None, verified: VerifiedFullBundleLicense | None,
                      trace_id: uuid.UUID) -> uuid.UUID: ...
    def attach_result(self, transaction: object, *, installation_id: uuid.UUID,
                      expected_version: int, event_id: uuid.UUID) -> bool: ...


class ValidationRecordingService:
    """No caller-supplied document or Verified result can become stored evidence."""

    def __init__(self, unit_of_work: Callable[[], object], repository: ValidationRecordingRepositoryPort,
                 validator: LicenseService, audit: AuditService) -> None:
        if any(item is None for item in (unit_of_work, repository, validator, audit)):
            raise ValueError("validation recording dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._validator = validator
        self._audit = audit

    def record_imported(self, installation_id: uuid.UUID, *, expected_lock_version: int,
                        expected_time_version: int, trace_id: uuid.UUID) -> RecordedValidation:
        if (type(installation_id) is not uuid.UUID or installation_id.int == 0
                or type(trace_id) is not uuid.UUID or trace_id.int == 0
                or type(expected_lock_version) is not int or expected_lock_version < 0
                or type(expected_time_version) is not int or expected_time_version < 0):
            raise ValidationRecordingError("TRUST_STATE_INVALID")
        with self._unit_of_work() as tx:
            source = self._repository.read_imported(tx, installation_id)
            if source is None:
                raise ValidationRecordingError("INSTALLATION_NOT_IMPORTED")
            if source.lock_version != expected_lock_version:
                raise ValidationRecordingError("INSTALLATION_CONFLICT")
        document = source.signed_document
        stored_hash = source.document_sha256
        trustworthy_document = (
            type(document) is bytes and 1 <= len(document) <= 65536
            and type(stored_hash) is bytes and len(stored_hash) == 32
            and hmac.compare_digest(hashlib.sha256(document).digest(), stored_hash)
        )
        verified = None
        code = "TRUST_STATE_INVALID"
        if trustworthy_document:
            try:
                verified = self._validator.validate(
                    document, expected_time_version=expected_time_version,
                    trace_id=trace_id, expected_public_key_ref=source.public_key_ref,
                )
                if not hmac.compare_digest(verified.document_sha256, stored_hash):
                    verified = None
                else:
                    code = "VALID"
            except LicenseValidationError as exc:
                code = exc.code
        with self._unit_of_work() as tx:
            current = self._repository.read_imported(tx, installation_id)
            if (current is None or current.lock_version != expected_lock_version
                    or current.public_key_ref != source.public_key_ref
                    or current.document_sha256 != stored_hash
                    or current.signed_document != document):
                raise ValidationRecordingError("INSTALLATION_CONFLICT")
            event_id = self._repository.append_result(
                tx, installation_id=installation_id, code=code,
                document_sha256=stored_hash if trustworthy_document else None,
                verified=verified, trace_id=trace_id,
            )
            if not self._repository.attach_result(tx, installation_id=installation_id,
                                                  expected_version=expected_lock_version, event_id=event_id):
                raise ValidationRecordingError("INSTALLATION_CONFLICT")
            self._audit.append(tx, AuditEventDraft(
                trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                actor_type="UNRESOLVED", actor_id=None, original_actor_id=None,
                actor_hint_digest=None, action="LICENSE_VALIDATION_RECORDED",
                outcome="SUCCESS" if code == "VALID" else "DENIED",
                target_owner_module="license", target_object_type="LIC-01",
                target_object_id=installation_id, target_version_id=None,
                reason_code=code,
            ))
            tx.commit()
        return RecordedValidation(installation_id, event_id, code, expected_lock_version + 1)
