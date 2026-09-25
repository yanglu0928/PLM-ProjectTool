"""PostgreSQL-backed UploadIntent creation and bounded replay lookup."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.create_upload_intent import (
    CreateUploadIntent, UploadIntentCreateError, UploadIntentSnapshot,
)
from plm_assistant.modules.document.infrastructure.orm import DocumentRow, UploadIntentRow
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyUploadIntentRepository:
    def creator_id(self, transaction: object, *, upload_id: uuid.UUID,
                   scope: str, project_id: uuid.UUID | None) -> uuid.UUID | None:
        return self._session(transaction).execute(select(UploadIntentRow.actor_id).where(
            UploadIntentRow.upload_id == upload_id,
            UploadIntentRow.scope == scope,
            UploadIntentRow.project_id == project_id,
        ).with_for_update(of=UploadIntentRow)).scalar_one_or_none()

    def create(self, transaction: object, *, command: CreateUploadIntent,
               upload_id: uuid.UUID, token_digest: bytes,
               ttl_seconds: int) -> UploadIntentSnapshot:
        session = self._session(transaction)
        if command.project_id is not None:
            state = session.execute(select(ProjectRow.state).where(
                ProjectRow.project_id == command.project_id,
            ).with_for_update(of=ProjectRow)).scalar_one_or_none()
            if state != "ACTIVE":
                raise UploadIntentCreateError("CONFLICT_STATE")
        if command.target_document_id is not None:
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == command.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            ).with_for_update(of=DocumentRow)).scalar_one_or_none()
            if document is None:
                raise UploadIntentCreateError("RESOURCE_NOT_FOUND")
            if document.document_state != "ACTIVE" or document.document_category == "GENERATED_ARTIFACT":
                raise UploadIntentCreateError("CONFLICT_STATE")
            if (command.supersedes_version_id is not None
                    and document.latest_version_ref != command.supersedes_version_id):
                raise UploadIntentCreateError("CONFLICT_VERSION")
        expires_at = session.execute(select(
            func.statement_timestamp() + timedelta(seconds=ttl_seconds)
        )).scalar_one()
        row = UploadIntentRow(
            upload_id=upload_id, scope=command.scope, project_id=command.project_id,
            actor_id=command.actor_id, target_document_id=command.target_document_id,
            document_category=command.document_category,
            document_subtype=command.document_subtype,
            document_purpose=command.document_purpose, title=command.title,
            original_display_name=command.original_display_name,
            purpose_code=command.purpose_code,
            expected_size_bytes=command.expected_size_bytes, mime_hint=command.mime_hint,
            token_digest=token_digest, expires_at=expires_at, state="CREATED",
        )
        session.add(row)
        session.flush()
        return UploadIntentSnapshot(upload_id, expires_at, token_digest)

    def replay(self, transaction: object, *, upload_id: uuid.UUID,
               command: CreateUploadIntent) -> UploadIntentSnapshot:
        session = self._session(transaction)
        row = session.execute(select(UploadIntentRow).where(
            UploadIntentRow.upload_id == upload_id,
            UploadIntentRow.actor_id == command.actor_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
        )).scalar_one_or_none()
        if row is None:
            raise UploadIntentCreateError("FILE_UNAVAILABLE")
        if command.project_id is not None and session.execute(select(ProjectRow.state).where(
            ProjectRow.project_id == command.project_id,
        )).scalar_one_or_none() != "ACTIVE":
            raise UploadIntentCreateError("CONFLICT_STATE")
        if command.target_document_id is not None:
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == command.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            )).scalar_one_or_none()
            if document is None or document.document_state != "ACTIVE":
                raise UploadIntentCreateError("CONFLICT_STATE")
            if (command.supersedes_version_id is not None
                    and document.latest_version_ref != command.supersedes_version_id):
                raise UploadIntentCreateError("CONFLICT_VERSION")
        now = session.execute(select(func.statement_timestamp())).scalar_one()
        if row.expires_at <= now or row.state not in ("CREATED", "CONTENT_READY"):
            raise UploadIntentCreateError("FILE_UPLOAD_EXPIRED")
        return UploadIntentSnapshot(row.upload_id, row.expires_at, row.token_digest)

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise UploadIntentCreateError("FILE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise UploadIntentCreateError("FILE_UNAVAILABLE")
        return session
