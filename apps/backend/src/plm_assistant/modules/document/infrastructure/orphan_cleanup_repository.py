"""Database eligibility for one unregistered upload staging file."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
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

    def pending_requests(self, transaction: object, *,
                         limit: int) -> tuple[tuple[uuid.UUID, str, uuid.UUID | None], ...]:
        if type(limit) is not int or not 1 <= limit <= 10_000:
            raise OrphanCleanupError("VALIDATION_FAILED")
        session = self._session(transaction)
        requested = self._audit_exists(
            UploadIntentRow.upload_id, ("DOCUMENT_ORPHAN_CLEANUP_REQUESTED",),
        )
        terminal = self._audit_exists(
            UploadIntentRow.upload_id,
            ("DOCUMENT_ORPHAN_CLEANUP_COMPLETED", "DOCUMENT_ORPHAN_CLEANUP_ABSENT"),
        )
        rows = session.execute(select(
            UploadIntentRow.upload_id, UploadIntentRow.scope,
            UploadIntentRow.project_id,
        ).where(requested, ~terminal).order_by(UploadIntentRow.created_at,
                                              UploadIntentRow.upload_id).limit(limit)).all()
        return tuple((row.upload_id, row.scope, row.project_id) for row in rows)

    def require_missing_reconciliation(self, transaction: object, *,
                                       command: CleanupUploadOrphan,
                                       ttl_seconds: int) -> bool:
        session = self._session(transaction)
        row = session.execute(select(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
        ).with_for_update(of=UploadIntentRow)).scalar_one_or_none()
        now = session.execute(select(func.statement_timestamp())).scalar_one()
        if (row is None or row.state not in ("CREATED", "ABORTED", "EXPIRED")
                or row.file_object_id is not None or row.document_version_id is not None
                or row.expires_at > now
                or row.created_at > now - timedelta(seconds=ttl_seconds)):
            raise OrphanCleanupError("CONFLICT_STATE")
        if session.execute(select(FileObjectRow.file_object_id).where(
            FileObjectRow.file_object_id == command.upload_id,
        )).scalar_one_or_none() is not None:
            raise OrphanCleanupError("CONFLICT_STATE")
        requested = session.execute(select(self._audit_exists(
            command.upload_id, ("DOCUMENT_ORPHAN_CLEANUP_REQUESTED",),
        ))).scalar_one()
        terminal = session.execute(select(self._audit_exists(
            command.upload_id,
            ("DOCUMENT_ORPHAN_CLEANUP_COMPLETED", "DOCUMENT_ORPHAN_CLEANUP_ABSENT"),
        ))).scalar_one()
        if not requested:
            raise OrphanCleanupError("CONFLICT_STATE")
        return not terminal

    @staticmethod
    def _audit_exists(upload_id, actions: tuple[str, ...]):
        return exists(select(AuditEventRow.audit_event_id).where(
            AuditEventRow.target_owner_module == "document",
            AuditEventRow.target_object_type == "DOC-03",
            AuditEventRow.target_object_id == upload_id,
            AuditEventRow.action.in_(actions),
        ))

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OrphanCleanupError("FILE_CONTENT_UNAVAILABLE")
        return session
