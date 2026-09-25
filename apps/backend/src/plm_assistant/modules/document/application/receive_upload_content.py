"""Internal two-phase upload content command; no public HTTP composition."""

from __future__ import annotations

import re
import hashlib
import hmac
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.document.infrastructure.content_spool import (
    StagedContentProof, ValidatedContentSpool,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError


_OPERATION = "V1_DOCUMENT_UPLOAD_CONTENT"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)


class UploadContentError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReceiveUploadContent:
    upload_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    upload_token: str = field(repr=False)
    declared_length: int
    declared_sha256: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class UploadContentIntent:
    original_display_name: str
    expected_size_bytes: int | None
    mime_hint: str | None
    replay: StagedContentProof | None = None


@dataclass(frozen=True, slots=True)
class ReceivedUploadContent:
    upload_id: uuid.UUID
    file_object_id: uuid.UUID
    size_bytes: int
    sha256: bytes = field(repr=False)
    detected_mime: str


class UploadContentAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               upload_id: uuid.UUID, operation: str) -> None: ...


class UploadContentRepositoryPort(Protocol):
    def preflight(self, transaction: object, *, command: ReceiveUploadContent) -> UploadContentIntent: ...
    def stage(self, transaction: object, *, command: ReceiveUploadContent,
              expected: UploadContentIntent, proof: StagedContentProof) -> uuid.UUID: ...
    def confirm_replay(self, transaction: object, *, command: ReceiveUploadContent,
                       expected: UploadContentIntent) -> uuid.UUID: ...


class UploadContentLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ReceiveUploadContentService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: UploadContentAccessPort,
                 repository: UploadContentRepositoryPort, audit: AuditService,
                 spool: ValidatedContentSpool, storage: LocalFileStorage,
                 license_guard: UploadContentLicensePort | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, repository, audit, spool, storage)):
            raise ValueError("Upload content dependencies are required")
        self._uow, self._access, self._repository = unit_of_work, access, repository
        self._audit, self._spool, self._storage = audit, spool, storage
        self._license_guard = license_guard

    def receive(self, command: ReceiveUploadContent, *, chunks: Iterable[bytes]) -> ReceivedUploadContent:
        self._validate(command)
        self._licensed(command)
        with self._uow() as tx:
            self._authorize(tx, command)
            intent = self._repository.preflight(tx, command=command)
        if intent.replay is not None:
            self._validate_replay_body(chunks, command)
            proof = intent.replay
            try:
                self._storage.verify_content(
                    proof.staging_locator, expected_sha256=proof.sha256,
                    expected_size=proof.size_bytes, max_bytes=command.declared_length,
                )
            except LocalStorageError:
                raise UploadContentError("FILE_INTEGRITY_MISMATCH") from None
            self._licensed(command)
            with self._uow() as tx:
                self._authorize(tx, command)
                file_id = self._repository.confirm_replay(
                    tx, command=command, expected=intent,
                )
            return ReceivedUploadContent(
                command.upload_id, file_id, proof.size_bytes,
                proof.sha256, proof.detected_mime,
            )
        claims = dict(
            scope=command.scope, project_id=command.project_id,
            file_object_id=command.upload_id,
            original_display_name=intent.original_display_name,
            declared_length=command.declared_length,
            declared_sha256=command.declared_sha256,
            mime_hint=intent.mime_hint,
            expected_size_bytes=intent.expected_size_bytes,
        )
        with self._spool.recover_existing(**claims) as recovered:
            if recovered is not None:
                self._validate_replay_body(chunks, command)
                return self._stage(command, intent, recovered)
        proof = self._spool.receive(chunks=chunks, **claims)
        # This second physical proof precedes the short DB transaction. The
        # later publish command must verify bytes again before making them visible.
        try:
            self._storage.verify_content(
                proof.staging_locator, expected_sha256=proof.sha256,
                expected_size=proof.size_bytes, max_bytes=command.declared_length,
            )
        except LocalStorageError:
            raise UploadContentError("FILE_INTEGRITY_MISMATCH") from None
        return self._stage(command, intent, proof)

    def _stage(self, command: ReceiveUploadContent, intent: UploadContentIntent,
               proof: StagedContentProof) -> ReceivedUploadContent:
        self._licensed(command)
        with self._uow() as tx:
            self._authorize(tx, command)
            file_id = self._repository.stage(
                tx, command=command, expected=intent, proof=proof,
            )
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id,
                event_scope="PROJECT" if command.scope == "PROJECT" else "DEPLOYMENT",
                target_project_id=command.project_id,
                actor_type="USER", actor_id=command.actor_id,
                original_actor_id=None, actor_hint_digest=None,
                action="DOCUMENT_UPLOAD_CONTENT_STAGED", outcome="SUCCESS",
                target_owner_module="document", target_object_type="DOC-03",
                target_object_id=command.upload_id,
                after_state="CONTENT_READY",
            ))
            tx.commit()
        return ReceivedUploadContent(
            command.upload_id, file_id, proof.size_bytes,
            proof.sha256, proof.detected_mime,
        )

    def _licensed(self, command: ReceiveUploadContent) -> None:
        if self._license_guard is not None:
            self._license_guard.require_valid(trace_id=command.trace_id)

    def _authorize(self, tx: object, command: ReceiveUploadContent) -> None:
        self._access.require_in_transaction(
            tx, actor_id=command.actor_id, scope=command.scope,
            project_id=command.project_id, upload_id=command.upload_id,
            operation=_OPERATION,
        )

    @staticmethod
    def _validate_replay_body(chunks: Iterable[bytes], command: ReceiveUploadContent) -> None:
        digest = hashlib.sha256()
        total = 0
        for chunk in chunks:
            if type(chunk) is not bytes or len(chunk) > 1_048_576:
                raise UploadContentError("VALIDATION_FAILED")
            total += len(chunk)
            if total > command.declared_length:
                raise UploadContentError("FILE_TOO_LARGE")
            digest.update(chunk)
        if (total != command.declared_length
                or not hmac.compare_digest(digest.digest(), command.declared_sha256)):
            raise UploadContentError("FILE_INTEGRITY_MISMATCH")

    @staticmethod
    def _validate(command: ReceiveUploadContent) -> None:
        if (type(command) is not ReceiveUploadContent
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.upload_id, command.actor_id, command.trace_id,
                ))
                or command.scope not in ("GLOBAL", "PROJECT")
                or command.scope == "GLOBAL" and command.project_id is not None
                or command.scope == "PROJECT" and (
                    type(command.project_id) is not uuid.UUID or command.project_id.int == 0)
                or type(command.upload_token) is not str or _TOKEN.fullmatch(command.upload_token) is None
                or type(command.declared_length) is not int or command.declared_length <= 0
                or type(command.declared_sha256) is not bytes or len(command.declared_sha256) != 32):
            raise UploadContentError("VALIDATION_FAILED")
