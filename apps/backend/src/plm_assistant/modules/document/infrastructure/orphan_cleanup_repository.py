"""Database eligibility for one unregistered upload staging file."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.cleanup_upload_orphan import (
    CleanupUploadOrphan, OrphanCleanupError,
)
from plm_assistant.modules.document.infrastructure.orm import FileObjectRow, UploadIntentRow


class SqlAlchemyOrphanCleanupRepository:
    def require_eligible(self, transaction: object, *, command: CleanupUploadOrphan,
                         ttl_seconds: int, modified_ns: int) -> int:
        session = self._session(transaction)
        row = session.execute(select(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
        ).with_for_update(of=UploadIntentRow)).scalar_one_or_none()
        now = session.execute(select(func.statement_timestamp())).scalar_one()
        cutoff = now - timedelta(seconds=ttl_seconds)
        if (row is None or row.state not in ("CREATED", "ABORTED", "EXPIRED")
                or row.file_object_id is not None or row.document_version_id is not None
                or row.created_at > cutoff or row.expires_at > now
                or modified_ns > int(cutoff.timestamp() * 1_000_000_000)):
            raise OrphanCleanupError("CONFLICT_STATE")
        if session.execute(select(FileObjectRow.file_object_id).where(
            FileObjectRow.file_object_id == command.upload_id,
        )).scalar_one_or_none() is not None:
            raise OrphanCleanupError("CONFLICT_STATE")
        return int(cutoff.timestamp() * 1_000_000_000)

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE")
        return session
