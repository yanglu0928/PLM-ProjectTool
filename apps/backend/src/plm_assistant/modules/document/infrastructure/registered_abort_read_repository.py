"""Conservative read-only database eligibility for aborted registered content."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.document.application.inspect_registered_abort import (
    RegisteredAbortCandidate, RegisteredAbortInspectionError,
)
from plm_assistant.modules.document.domain.file_state import transition_requirements
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentVersionRow, FileObjectRow, FileStateEventRow, UploadIntentRow,
)


class SqlAlchemyRegisteredAbortReadRepository:
    def candidate(self, transaction: object, upload_id: uuid.UUID, *,
                  lock: bool = False) -> RegisteredAbortCandidate | None:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise RegisteredAbortInspectionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise RegisteredAbortInspectionError()
        intent = session.get(UploadIntentRow, upload_id, with_for_update=lock)
        if (intent is None or intent.state != "ABORTED"
                or intent.file_object_id != upload_id
                or intent.document_version_id is not None
                or intent.committed_document_id is not None):
            return None
        file = session.get(FileObjectRow, upload_id, with_for_update=lock)
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

    def requested(self, transaction: object, upload_id: uuid.UUID) -> bool:
        session = self._session(transaction)
        return session.execute(select(AuditEventRow.audit_event_id).where(
            AuditEventRow.target_owner_module == "document",
            AuditEventRow.target_object_type == "DOC-03",
            AuditEventRow.target_object_id == upload_id,
            AuditEventRow.action == "DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED",
        ).limit(1)).first() is not None

    def completed(self, transaction: object, *, upload_id: uuid.UUID,
                  scope: str, project_id: uuid.UUID | None) -> bool:
        session = self._session(transaction)
        intent = session.get(UploadIntentRow, upload_id)
        file = session.get(FileObjectRow, upload_id)
        if (intent is None or file is None or intent.state != "ABORTED"
                or intent.scope != scope or intent.project_id != project_id
                or intent.file_object_id != upload_id or file.file_state != "REMOVED"
                or file.scope != scope or file.project_id != project_id):
            return False
        return session.execute(select(AuditEventRow.audit_event_id).where(
            AuditEventRow.target_owner_module == "document",
            AuditEventRow.target_object_type == "DOC-03",
            AuditEventRow.target_object_id == upload_id,
            AuditEventRow.action.in_((
                "DOCUMENT_REGISTERED_ABORT_CLEANUP_COMPLETED",
                "DOCUMENT_REGISTERED_ABORT_CLEANUP_ABSENT",
            )),
        ).limit(1)).first() is not None

    def mark_removed(self, transaction: object, *, expected: RegisteredAbortCandidate,
                     actor_id: uuid.UUID, trace_id: uuid.UUID,
                     reconciled_absent: bool) -> None:
        current = self.candidate(transaction, expected.upload_id, lock=True)
        if current != expected:
            raise RegisteredAbortInspectionError()
        transition_requirements(from_state="CLEANUP_PENDING", to_state="REMOVED",
                                storage_class="PERSISTENT")
        session = self._session(transaction)
        reason = ("REGISTERED_ABORT_ABSENT_RECONCILED" if reconciled_absent
                  else "REGISTERED_ABORT_CLEANED")
        changed = session.execute(update(FileObjectRow).where(
            FileObjectRow.file_object_id == expected.upload_id,
            FileObjectRow.file_state == "CLEANUP_PENDING",
            FileObjectRow.lock_version == expected.file_lock_version,
        ).values(
            file_state="REMOVED", updated_by=actor_id,
            updated_at=func.statement_timestamp(),
            lock_version=FileObjectRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise RegisteredAbortInspectionError()
        session.execute(insert(FileStateEventRow).values(
            file_state_event_id=uuid.uuid4(), file_object_id=expected.upload_id,
            from_state="CLEANUP_PENDING", to_state="REMOVED",
            reason_code=reason, actor_user_id=actor_id, trace_id=trace_id,
        ))

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise RegisteredAbortInspectionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise RegisteredAbortInspectionError()
        return session
