"""Conservative read-only database eligibility for aborted registered content."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.inspect_registered_abort import (
    RegisteredAbortCandidate, RegisteredAbortInspectionError,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentVersionRow, FileObjectRow, UploadIntentRow,
)


class SqlAlchemyRegisteredAbortReadRepository:
    def candidate(self, transaction: object, upload_id: uuid.UUID) -> RegisteredAbortCandidate | None:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise RegisteredAbortInspectionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise RegisteredAbortInspectionError()
        intent = session.get(UploadIntentRow, upload_id)
        if (intent is None or intent.state != "ABORTED"
                or intent.file_object_id != upload_id
                or intent.document_version_id is not None
                or intent.committed_document_id is not None):
            return None
        file = session.get(FileObjectRow, upload_id)
        if (file is None or file.file_object_id != intent.file_object_id
                or file.scope != intent.scope or file.project_id != intent.project_id
                or file.storage_class != "PERSISTENT"
                or file.file_state != "CLEANUP_PENDING"
                or file.failure_code != "UPLOAD_ABORTED"
                or file.retention_due_at is not None or file.available_at is not None
                or type(file.sha256) is not bytes or len(file.sha256) != 32
                or type(file.size_bytes) is not int
                or not 0 <= file.size_bytes <= 100_000_000):
            return None
        if session.execute(select(DocumentVersionRow.document_version_id).where(
            DocumentVersionRow.file_object_id == upload_id,
        )).first() is not None:
            return None
        try:
            stage, final = LocalFileStorage.locators(
                scope=intent.scope, project_id=intent.project_id,
                file_object_id=upload_id,
            )
        except LocalStorageError:
            return None
        if file.storage_locator != stage:
            return None
        return RegisteredAbortCandidate(
            upload_id, intent.scope, intent.project_id, stage, final,
            file.sha256, file.size_bytes, file.lock_version, intent.lock_version,
        )
