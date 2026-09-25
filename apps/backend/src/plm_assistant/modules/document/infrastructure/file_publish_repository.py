"""Row-scoped FileObject publication with an atomic state event."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.publish_file import (
    FilePublishError, PublishFile, StagedFile,
)
from plm_assistant.modules.document.domain.file_state import (
    FileStateTransitionError, transition_requirements,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow, FileStateEventRow


class SqlAlchemyFilePublishRepository:
    def staged(self, transaction: object, *, command: PublishFile) -> StagedFile:
        row = self._row(transaction, command, lock=False)
        if row is None:
            raise FilePublishError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise FilePublishError("CONFLICT_VERSION")
        try:
            requirements = transition_requirements(
                from_state=row.file_state, to_state="AVAILABLE",
                storage_class=row.storage_class,
            )
            stage, final = LocalFileStorage.locators(
                scope=command.scope, project_id=command.project_id,
                file_object_id=command.file_object_id,
            )
        except (FileStateTransitionError, LocalStorageError):
            raise FilePublishError("CONFLICT_STATE") from None
        if (row.storage_class != "PERSISTENT" or not requirements.verify_final_content
                or row.storage_locator != stage or type(row.sha256) is not bytes
                or len(row.sha256) != 32 or type(row.size_bytes) is not int
                or row.size_bytes < 0 or row.size_bytes > command.max_bytes
                or type(row.detected_mime) is not str or not row.detected_mime
                or row.available_at is not None):
            raise FilePublishError("FILE_UNAVAILABLE")
        return StagedFile(stage, final, row.sha256, row.size_bytes)

    def publish(self, transaction: object, *, command: PublishFile,
                expected: StagedFile) -> uuid.UUID:
        row = self._row(transaction, command, lock=True)
        if row is None:
            raise FilePublishError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise FilePublishError("CONFLICT_VERSION")
        current = self.staged(transaction, command=command)
        if current != expected:
            raise FilePublishError("CONFLICT_VERSION")
        session = transaction.session  # type: ignore[attr-defined]
        result = session.execute(update(FileObjectRow).where(
            FileObjectRow.file_object_id == command.file_object_id,
            FileObjectRow.lock_version == command.expected_version,
            FileObjectRow.file_state == "STAGED",
        ).values(
            file_state="AVAILABLE", storage_locator=expected.final_locator,
            available_at=func.statement_timestamp(), updated_at=func.statement_timestamp(),
            updated_by=command.actor_id, lock_version=FileObjectRow.lock_version + 1,
        ))
        if result.rowcount != 1:
            raise FilePublishError("CONFLICT_VERSION")
        event_id = uuid.uuid4()
        session.execute(insert(FileStateEventRow).values(
            file_state_event_id=event_id, file_object_id=command.file_object_id,
            from_state="STAGED", to_state="AVAILABLE", reason_code=None,
            actor_user_id=command.actor_id, trace_id=command.trace_id,
        ))
        return event_id

    @staticmethod
    def _row(transaction: object, command: PublishFile, *, lock: bool):
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise FilePublishError("FILE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise FilePublishError("FILE_UNAVAILABLE")
        query = select(FileObjectRow).where(
            FileObjectRow.file_object_id == command.file_object_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        )
        if lock:
            query = query.with_for_update(of=FileObjectRow)
        return session.execute(query).scalar_one_or_none()
