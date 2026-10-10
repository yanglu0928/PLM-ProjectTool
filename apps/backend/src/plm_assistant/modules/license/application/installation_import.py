"""Internal, authenticated import of a signed License candidate."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.license.application.license_validation import ProductPublicKeyPort
from plm_assistant.modules.license.application.signature_verifier import (
    LicenseSignatureError, LicenseSignatureVerifier, MAX_DOCUMENT_BYTES,
)


_KEY_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)


class LicenseImportError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ImportLicense:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    signed_document: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ImportResult:
    installation_id: uuid.UUID | None
    validation_event_id: uuid.UUID | None
    code: str


class LicenseImportAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None:
        """Return authenticated DeploymentAdmin user ID, or deny."""


class LicenseImportRepositoryPort(Protocol):
    def add_imported(self, transaction: object, *, public_key_ref: str,
                     actor_id: uuid.UUID, trace_id: uuid.UUID,
                     signed_document: bytes, document_sha256: bytes) -> uuid.UUID: ...
    def append_rejection(self, transaction: object, *, code: str,
                         trace_id: uuid.UUID, document_sha256: bytes) -> uuid.UUID: ...


class LicenseImportService:
    def __init__(self, *, unit_of_work: Callable[[], object], repository: LicenseImportRepositoryPort,
                 access: LicenseImportAccessPort, signature: LicenseSignatureVerifier,
                 product_key: ProductPublicKeyPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, repository, access, signature, product_key, audit)):
            raise ValueError("license import dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._access = access
        self._signature = signature
        self._product_key = product_key
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def import_candidate(self, command: ImportLicense) -> ImportResult:
        if (type(command) is not ImportLicense
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.signed_document) is not bytes
                or not 1 <= len(command.signed_document) <= MAX_DOCUMENT_BYTES
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise LicenseImportError("VALIDATION_FAILED")
        try:
            now = self._clock()
            key_ref = self._product_key.product_key_ref()
        except Exception:
            raise LicenseImportError("TRUST_STATE_INVALID") from None
        if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
                or type(key_ref) is not str or not _KEY_REF.fullmatch(key_ref)):
            raise LicenseImportError("TRUST_STATE_INVALID")
        digest = hashlib.sha256(command.signed_document).digest()
        with self._unit_of_work() as tx:
            actor_id = self._access.authorized_admin(
                tx, session_token=command.session_token,
                csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
            )
            if type(actor_id) is not uuid.UUID or actor_id.int == 0:
                raise LicenseImportError("AUTH_ACCESS_DENIED")
            try:
                verified = self._signature.verify(command.signed_document, public_key_ref=key_ref)
            except LicenseSignatureError as exc:
                code = {
                    "LICENSE_SIGNATURE_INVALID": "SIGNATURE_INVALID",
                    "LICENSE_DOCUMENT_INVALID": "MALFORMED",
                }.get(exc.code, "TRUST_STATE_INVALID")
                event_id = self._repository.append_rejection(
                    tx, code=code, trace_id=command.trace_id, document_sha256=digest,
                )
                self._audit.append(tx, _audit(command.trace_id, actor_id, None, "DENIED", code))
                tx.commit()
                return ImportResult(None, event_id, code)
            if verified.public_key_ref != key_ref or verified.document_sha256 != digest:
                raise LicenseImportError("TRUST_STATE_INVALID")
            installation_id = self._repository.add_imported(
                tx, public_key_ref=key_ref, actor_id=actor_id, trace_id=command.trace_id,
                signed_document=command.signed_document, document_sha256=digest,
            )
            self._audit.append(tx, _audit(command.trace_id, actor_id, installation_id,
                                          "SUCCESS", "IMPORTED"))
            tx.commit()
            return ImportResult(installation_id, None, "IMPORTED")


def _audit(trace_id: uuid.UUID, actor_id: uuid.UUID, installation_id: uuid.UUID | None,
           outcome: str, code: str) -> AuditEventDraft:
    return AuditEventDraft(
        trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
        actor_type="USER", actor_id=actor_id, original_actor_id=None,
        actor_hint_digest=None, action="LICENSE_IMPORT", outcome=outcome,
        target_owner_module="license" if installation_id else None,
        target_object_type="LIC-01" if installation_id else None,
        target_object_id=installation_id, reason_code=code,
        after_state="IMPORTED" if installation_id else None,
    )
