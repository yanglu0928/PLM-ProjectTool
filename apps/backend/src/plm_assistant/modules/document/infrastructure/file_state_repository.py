"""Document-owned row-locked FileObject fail/restrict updates and events."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.change_file_state import (
    ChangeFileState, FileStateCommandError,
)
from plm_assistant.modules.document.domain.file_state import (
    FileStateTransitionError, transition_requirements,
)
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow, FileStateEventRow


class SqlAlchemyFileStateRepository:
    def change(self, transaction: object, *, command: ChangeFileState) -> uuid.UUID:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise FileStateCommandError("FILE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise FileStateCommandError("FILE_UNAVAILABLE")
        row = session.execute(select(FileObjectRow).where(
            FileObjectRow.file_object_id == command.file_object_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        ).with_for_update(of=FileObjectRow)).scalar_one_or_none()
        if row is None:
            raise FileStateCommandError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise FileStateCommandError("CONFLICT_VERSION")
        try:
            requirements = transition_requirements(
                from_state=row.file_state, to_state=command.target_state,
                storage_class=row.storage_class,
            )
        except FileStateTransitionError:
            raise FileStateCommandError("CONFLICT_STATE") from None
        if (command.target_state not in ("FAILED", "RESTRICTED")
                or requirements.verify_final_content
                or requirements.verify_cleanup_eligibility
                or not requirements.record_reason):
            raise FileStateCommandError("CONFLICT_STATE")
        before_state = row.file_state
        result = session.execute(update(FileObjectRow).where(
            FileObjectRow.file_object_id == command.file_object_id,
            FileObjectRow.lock_version == command.expected_version,
        ).values(
            file_state=command.target_state,
            failure_code=command.reason_code if command.target_state == "FAILED" else row.failure_code,
            updated_by=command.actor_id,
            updated_at=func.statement_timestamp(),
            lock_version=FileObjectRow.lock_version + 1,
        ))
        if result.rowcount != 1:
            raise FileStateCommandError("CONFLICT_VERSION")
        event_id = uuid.uuid4()
        session.execute(insert(FileStateEventRow).values(
            file_state_event_id=event_id,
            file_object_id=command.file_object_id,
            from_state=before_state, to_state=command.target_state,
            reason_code=command.reason_code, actor_user_id=command.actor_id,
            trace_id=command.trace_id,
        ))
        return event_id
