"""Row-locked UploadIntent Abort and registered FileObject cleanup scheduling."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.abort_upload import (
    AbortUpload, AbortedUpload, UploadAbortError,
)
from plm_assistant.modules.document.domain.file_state import transition_requirements
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow, FileStateEventRow, UploadIntentRow,
)
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyUploadAbortRepository:
    def abort(self, transaction: object, *, command: AbortUpload) -> AbortedUpload:
        session = self._session(transaction)
        if command.project_id is not None:
            project = session.execute(select(ProjectRow).where(
                ProjectRow.project_id == command.project_id,
            ).with_for_update(of=ProjectRow)).scalar_one_or_none()
            if project is None or project.state != "ACTIVE":
                raise UploadAbortError("PROJECT_ARCHIVED")
        # Match the Commit lock sequence. The unlocked lookup is only a lock-order hint;
        # the locked row is checked again before any mutation.
        target_id = session.execute(select(UploadIntentRow.target_document_id).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
            UploadIntentRow.actor_id == command.actor_id,
        )).scalar_one_or_none()
        if target_id is not None:
            session.execute(select(DocumentRow).where(
                DocumentRow.document_id == target_id,
            ).with_for_update(of=DocumentRow)).scalar_one_or_none()
        intent = self._intent(session, command, lock=True)
        if intent is None:
            raise UploadAbortError("RESOURCE_NOT_FOUND")
        if intent.target_document_id != target_id or intent.state not in ("CREATED", "CONTENT_READY"):
            raise UploadAbortError("CONFLICT_STATE")
        has_file = intent.state == "CONTENT_READY"
        if has_file:
            self._schedule_file_cleanup(session, command, intent)
        elif intent.file_object_id is not None:
            raise UploadAbortError("CONFLICT_STATE")
        changed = session.execute(update(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.lock_version == intent.lock_version,
            UploadIntentRow.state == intent.state,
        ).values(
            state="ABORTED", lock_version=UploadIntentRow.lock_version + 1,
            updated_at=func.statement_timestamp(),
        ))
        if changed.rowcount != 1:
            raise UploadAbortError("CONFLICT_STATE")
        return AbortedUpload(command.upload_id, has_file)

    def replay(self, transaction: object, *, command: AbortUpload) -> AbortedUpload:
        intent = self._intent(self._session(transaction), command, lock=False)
        if intent is None or intent.state != "ABORTED":
            raise UploadAbortError("CONFLICT_STATE")
        return AbortedUpload(command.upload_id, intent.file_object_id is not None)

    @staticmethod
    def _schedule_file_cleanup(session: Session, command: AbortUpload,
                               intent: UploadIntentRow) -> None:
        if intent.file_object_id != command.upload_id:
            raise UploadAbortError("FILE_UNAVAILABLE")
        file = session.execute(select(FileObjectRow).where(
            FileObjectRow.file_object_id == intent.file_object_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        ).with_for_update(of=FileObjectRow)).scalar_one_or_none()
        if file is None or file.file_state != "STAGED" or file.storage_class != "PERSISTENT":
            raise UploadAbortError("FILE_UNAVAILABLE")
        try:
            stage, _ = LocalFileStorage.locators(
                scope=command.scope, project_id=command.project_id,
                file_object_id=command.upload_id,
            )
            transition_requirements(from_state="STAGED", to_state="FAILED",
                                    storage_class=file.storage_class)
            transition_requirements(from_state="FAILED", to_state="CLEANUP_PENDING",
                                    storage_class=file.storage_class)
        except (LocalStorageError, ValueError):
            raise UploadAbortError("FILE_UNAVAILABLE") from None
        if (file.storage_locator != stage or file.sha256 is None
                or file.size_bytes is None or file.detected_mime is None
                or session.execute(select(DocumentVersionRow.document_version_id).where(
                    DocumentVersionRow.file_object_id == file.file_object_id,
                )).first() is not None):
            raise UploadAbortError("FILE_UNAVAILABLE")
        for before, after in (("STAGED", "FAILED"), ("FAILED", "CLEANUP_PENDING")):
            changed = session.execute(update(FileObjectRow).where(
                FileObjectRow.file_object_id == file.file_object_id,
                FileObjectRow.file_state == before,
            ).values(
                file_state=after, failure_code="UPLOAD_ABORTED",
                updated_by=command.actor_id,
                updated_at=func.statement_timestamp(),
                lock_version=FileObjectRow.lock_version + 1,
            ))
            if changed.rowcount != 1:
                raise UploadAbortError("CONFLICT_STATE")
            session.execute(insert(FileStateEventRow).values(
                file_state_event_id=uuid.uuid4(),
                file_object_id=file.file_object_id,
                from_state=before, to_state=after,
                reason_code="UPLOAD_ABORTED", actor_user_id=command.actor_id,
                trace_id=command.trace_id,
            ))

    @staticmethod
    def _intent(session: Session, command: AbortUpload, *, lock: bool) -> UploadIntentRow | None:
        query = select(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
            UploadIntentRow.actor_id == command.actor_id,
        )
        if lock:
            query = query.with_for_update(of=UploadIntentRow)
        return session.execute(query).scalar_one_or_none()

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise UploadAbortError("DOCUMENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise UploadAbortError("DOCUMENT_UNAVAILABLE")
        return session
