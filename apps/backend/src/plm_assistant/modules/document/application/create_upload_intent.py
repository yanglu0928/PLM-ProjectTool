"""Internal, idempotent creation of a short-lived upload intent."""

from __future__ import annotations

import hmac
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_DOCUMENT_UPLOAD_CREATE"
_CATEGORIES = frozenset((
    "CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
    "REFERENCE_MATERIAL", "TEMPLATE", "OTHER",
))
_PURPOSE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)


class UploadIntentCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateUploadIntent:
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    purpose_code: str
    target_document_id: uuid.UUID | None = None
    document_category: str | None = None
    document_subtype: str | None = None
    document_purpose: str | None = None
    title: str | None = None
    original_display_name: str | None = None
    expected_size_bytes: int | None = None
    mime_hint: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedUploadIntent:
    upload_id: uuid.UUID
    expires_at: datetime
    upload_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class UploadIntentSnapshot:
    upload_id: uuid.UUID
    expires_at: datetime
    token_digest: bytes = field(repr=False)


class UploadCreateAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               target_document_id: uuid.UUID | None,
                               operation: str) -> None: ...


class UploadTokenIssuerPort(Protocol):
    def issue(self, *, upload_id: uuid.UUID, actor_id: uuid.UUID,
              scope: str, project_id: uuid.UUID | None) -> tuple[str, bytes]: ...


class UploadIntentRepositoryPort(Protocol):
    def create(self, transaction: object, *, command: CreateUploadIntent,
               upload_id: uuid.UUID, token_digest: bytes,
               ttl_seconds: int) -> UploadIntentSnapshot: ...
    def replay(self, transaction: object, *, upload_id: uuid.UUID,
               command: CreateUploadIntent) -> UploadIntentSnapshot: ...


class UploadCreateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class CreateUploadIntentService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: UploadCreateAccessPort,
                 repository: UploadIntentRepositoryPort, receipts: UploadCreateReceiptPort,
                 audit: AuditService, token_issuer: UploadTokenIssuerPort,
                 ttl_seconds: int = 900, max_bytes: int = 100_000_000) -> None:
        if any(value is None for value in (unit_of_work, access, repository, receipts, audit, token_issuer)):
            raise ValueError("Upload intent dependencies are required")
        if (type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 3600
                or type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("Invalid upload intent limits")
        self._uow, self._access, self._repository = unit_of_work, access, repository
        self._receipts, self._audit, self._issuer = receipts, audit, token_issuer
        self._ttl, self._max_bytes = ttl_seconds, max_bytes

    def create(self, command: CreateUploadIntent, *, idempotency_key: str) -> CreatedUploadIntent:
        self._validate(command)
        validate_idempotency_key(idempotency_key)
        fingerprint = canonical_payload_fingerprint({
            "scope": command.scope, "project_id": str(command.project_id),
            "target_document_id": str(command.target_document_id),
            "category": command.document_category, "subtype": command.document_subtype,
            "document_purpose": command.document_purpose, "title": command.title,
            "display_name": command.original_display_name,
            "purpose_code": command.purpose_code,
            "expected_size_bytes": command.expected_size_bytes, "mime_hint": command.mime_hint,
        })
        scope = IdempotencyScope.from_key(
            actor_id=command.actor_id, project_id=command.project_id,
            operation=_OPERATION, key=idempotency_key,
        )
        with self._uow() as tx:
            self._access.require_in_transaction(
                tx, actor_id=command.actor_id, scope=command.scope,
                project_id=command.project_id,
                target_document_id=command.target_document_id,
                operation=_OPERATION,
            )
            replay = self._receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint)
            if replay is not None:
                if replay.ref_type != _OPERATION or replay.status_code != 201:
                    raise UploadIntentCreateError("FILE_UNAVAILABLE")
                snapshot = self._repository.replay(tx, upload_id=replay.ref_id, command=command)
            else:
                upload_id = uuid.uuid4()
                token, digest = self._issuer.issue(
                    upload_id=upload_id, actor_id=command.actor_id,
                    scope=command.scope, project_id=command.project_id,
                )
                snapshot = self._repository.create(
                    tx, command=command, upload_id=upload_id,
                    token_digest=digest, ttl_seconds=self._ttl,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=command.actor_id,
                    original_actor_id=None, actor_hint_digest=None,
                    action="DOCUMENT_UPLOAD_CREATE", outcome="SUCCESS",
                    target_owner_module="document", target_object_type="DOC-03",
                    target_object_id=upload_id, after_state="CREATED",
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(_OPERATION, upload_id, 201),
                )
            if replay is not None:
                token, digest = self._issuer.issue(
                    upload_id=snapshot.upload_id, actor_id=command.actor_id,
                    scope=command.scope, project_id=command.project_id,
                )
            if not hmac.compare_digest(digest, snapshot.token_digest):
                raise UploadIntentCreateError("FILE_UNAVAILABLE")
            tx.commit()
            return CreatedUploadIntent(snapshot.upload_id, snapshot.expires_at, token)

    def _validate(self, command: CreateUploadIntent) -> None:
        if (type(command) is not CreateUploadIntent
                or command.scope not in ("GLOBAL", "PROJECT")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and not self._uuid(command.project_id)
                or not self._uuid(command.actor_id) or not self._uuid(command.trace_id)
                or command.target_document_id is not None and not self._uuid(command.target_document_id)
                or type(command.purpose_code) is not str or not _PURPOSE.fullmatch(command.purpose_code)
                or command.expected_size_bytes is not None and (
                    type(command.expected_size_bytes) is not int
                    or not 0 <= command.expected_size_bytes <= self._max_bytes)
                or command.mime_hint is not None and not self._label(command.mime_hint, 255)):
            raise UploadIntentCreateError("VALIDATION_FAILED")
        if command.target_document_id is not None:
            if any(value is not None for value in (
                command.document_category, command.document_subtype,
                command.document_purpose, command.title,
            )) or not self._label(command.original_display_name, 255):
                raise UploadIntentCreateError("VALIDATION_FAILED")
        elif (command.document_category not in _CATEGORIES
              or not self._label(command.title, 255)
              or not self._label(command.original_display_name, 255)
              or command.document_subtype is not None and not self._label(command.document_subtype, 128)
              or command.document_purpose is not None and not self._label(command.document_purpose, 255)
              or command.document_category == "OTHER" and (
                  command.document_subtype is None or command.document_purpose is None)):
            raise UploadIntentCreateError("VALIDATION_FAILED")

    @staticmethod
    def _uuid(value: object) -> bool:
        return type(value) is uuid.UUID and value.int != 0

    @staticmethod
    def _label(value: object, limit: int) -> bool:
        return (type(value) is str and 1 <= len(value) <= limit and value == value.strip()
                and not any(ord(char) < 32 or ord(char) == 127 for char in value))
