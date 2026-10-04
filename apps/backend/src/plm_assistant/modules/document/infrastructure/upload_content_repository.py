"""Transactional UploadIntent and FileObject state coupling for Content."""

from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, UploadContentError, UploadContentIntent,
)
from plm_assistant.modules.document.infrastructure.content_spool import StagedContentProof
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, FileObjectRow, FileStateEventRow, UploadIntentRow,
)
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyUploadContentRepository:
    def preflight(self, transaction: object, *, command: ReceiveUploadContent) -> UploadContentIntent:
        session = self._session(transaction)
        row = self._intent(session, command, lock=False)
        self._check(session, row, command, allow_ready=True)
        replay = self._replay_proof(session, row, command) if row.state == "CONTENT_READY" else None
        return UploadContentIntent(
            row.original_display_name, row.expected_size_bytes, row.mime_hint, replay,
        )

    def confirm_replay(self, transaction: object, *, command: ReceiveUploadContent,
                       expected: UploadContentIntent) -> uuid.UUID:
        session = self._session(transaction)
        if command.project_id is not None and session.execute(select(ProjectRow.state).where(
            ProjectRow.project_id == command.project_id,
        ).with_for_update(of=ProjectRow)).scalar_one_or_none() != "ACTIVE":
            raise UploadContentError("PROJECT_ARCHIVED")
        pre = self._intent(session, command, lock=False)
        if pre is None:
            raise UploadContentError("RESOURCE_NOT_FOUND")
        if pre.target_document_id is not None:
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == pre.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            ).with_for_update(of=DocumentRow)).scalar_one_or_none()
            if document is None or document.document_state != "ACTIVE":
                raise UploadContentError("CONFLICT_STATE")
        row = self._intent(session, command, lock=True)
        self._check(session, row, command, allow_ready=True)
        if row.state != "CONTENT_READY" or expected.replay is None:
            raise UploadContentError("CONFLICT_STATE")
        proof = self._replay_proof(session, row, command)
        if (UploadContentIntent(row.original_display_name, row.expected_size_bytes,
                                row.mime_hint, proof) != expected):
            raise UploadContentError("CONFLICT_STATE")
        return row.file_object_id

    def stage(self, transaction: object, *, command: ReceiveUploadContent,
              expected: UploadContentIntent, proof: StagedContentProof) -> uuid.UUID:
        session = self._session(transaction)
        if command.project_id is not None and session.execute(select(ProjectRow.state).where(
            ProjectRow.project_id == command.project_id,
        ).with_for_update(of=ProjectRow)).scalar_one_or_none() != "ACTIVE":
            raise UploadContentError("PROJECT_ARCHIVED")
        # Keep the same lock order as Document commits: Project, Document,
        # then this upload-control row and its new FileObject.
        pre = self._intent(session, command, lock=False)
        if pre is None:
            raise UploadContentError("RESOURCE_NOT_FOUND")
        if pre.target_document_id is not None:
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == pre.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            ).with_for_update(of=DocumentRow)).scalar_one_or_none()
            if document is None or document.document_state != "ACTIVE":
                raise UploadContentError("CONFLICT_STATE")
        row = self._intent(session, command, lock=True)
        self._check(session, row, command)
        if UploadContentIntent(row.original_display_name, row.expected_size_bytes, row.mime_hint) != expected:
            raise UploadContentError("CONFLICT_STATE")
        stage_locator, _ = LocalFileStorage.locators(
            scope=command.scope, project_id=command.project_id,
            file_object_id=command.upload_id,
        )
        if (type(proof) is not StagedContentProof
                or proof.staging_locator != stage_locator
                or proof.sha256 != command.declared_sha256
                or proof.size_bytes != command.declared_length
                or type(proof.detected_mime) is not str or not proof.detected_mime):
            raise UploadContentError("FILE_INTEGRITY_MISMATCH")
        file_id = command.upload_id
        session.add(FileObjectRow(
            file_object_id=file_id, scope=command.scope, project_id=command.project_id,
            storage_class="PERSISTENT", storage_locator=stage_locator,
            original_name_metadata=row.original_display_name,
            sha256=proof.sha256, size_bytes=proof.size_bytes,
            detected_mime=proof.detected_mime,
            file_state="STAGED", created_by=command.actor_id,
        ))
        session.flush()
        session.add(FileStateEventRow(
            file_state_event_id=uuid.uuid4(), file_object_id=file_id,
            from_state=None, to_state="STAGED", reason_code=None,
            actor_user_id=command.actor_id, trace_id=command.trace_id,
        ))
        changed = session.execute(update(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.lock_version == row.lock_version,
            UploadIntentRow.state == "CREATED",
        ).values(
            state="CONTENT_READY", file_object_id=file_id,
            updated_at=func.statement_timestamp(),
            lock_version=UploadIntentRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise UploadContentError("CONFLICT_STATE")
        session.flush()
        return file_id

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise UploadContentError("FILE_CONTENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise UploadContentError("FILE_CONTENT_UNAVAILABLE")
        return session

    @staticmethod
    def _intent(session: Session, command: ReceiveUploadContent, *, lock: bool):
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
    def _check(session: Session, row, command: ReceiveUploadContent, *,
               allow_ready: bool = False) -> None:
        if row is None:
            raise UploadContentError("RESOURCE_NOT_FOUND")
        if not hmac.compare_digest(
            hashlib.sha256(command.upload_token.encode("ascii")).digest(), row.token_digest,
        ):
            raise UploadContentError("AUTH_ACCESS_DENIED")
        if row.expires_at <= session.execute(select(func.statement_timestamp())).scalar_one():
            raise UploadContentError("FILE_UPLOAD_EXPIRED")
        if row.state != "CREATED" and not (allow_ready and row.state == "CONTENT_READY"):
            raise UploadContentError("CONFLICT_STATE")
        if row.original_display_name is None:
            raise UploadContentError("CONFLICT_STATE")
        if row.expected_size_bytes is not None and row.expected_size_bytes != command.declared_length:
            raise UploadContentError("FILE_INTEGRITY_MISMATCH")
        if command.project_id is not None and session.execute(select(ProjectRow.state).where(
            ProjectRow.project_id == command.project_id,
        )).scalar_one_or_none() != "ACTIVE":
            raise UploadContentError("PROJECT_ARCHIVED")

    @staticmethod
    def _replay_proof(session: Session, row, command: ReceiveUploadContent) -> StagedContentProof:
        locator, _ = LocalFileStorage.locators(
            scope=command.scope, project_id=command.project_id,
            file_object_id=command.upload_id,
        )
        file = session.execute(select(FileObjectRow).where(
            FileObjectRow.file_object_id == command.upload_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        )).scalar_one_or_none()
        if (row.file_object_id != command.upload_id or file is None
                or file.file_state != "STAGED" or file.storage_class != "PERSISTENT"
                or file.storage_locator != locator
                or file.original_name_metadata != row.original_display_name
                or file.sha256 != command.declared_sha256
                or file.size_bytes != command.declared_length
                or type(file.detected_mime) is not str or not file.detected_mime):
            raise UploadContentError("CONFLICT_STATE")
        return StagedContentProof(locator, file.sha256, file.size_bytes, file.detected_mime)
