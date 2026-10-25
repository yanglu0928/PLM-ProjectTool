"""Document-owned upload commit; all database mutations share caller transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommittedUploadVersion, ReadyUpload, UploadCommitError,
)
from plm_assistant.modules.document.application.commit_upload_version import (
    CommitUploadVersion, PublishedFileSnapshot,
)
from plm_assistant.modules.document.application.publish_file import PublishFile, StagedFile
from plm_assistant.modules.document.infrastructure.file_publish_repository import SqlAlchemyFilePublishRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow, UploadIntentRow,
)
from plm_assistant.modules.document.infrastructure.upload_version_repository import SqlAlchemyUploadVersionRepository
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyUploadCommitRepository:
    def __init__(self) -> None:
        self._file_publisher = SqlAlchemyFilePublishRepository()
        self._version_writer = SqlAlchemyUploadVersionRepository()

    def preflight(self, transaction: object, *, command: CommitUpload) -> ReadyUpload:
        session = self._session(transaction)
        intent = self._intent(session, command, lock=False)
        if intent is None:
            raise UploadCommitError("RESOURCE_NOT_FOUND")
        return self._ready(session, transaction, intent, command)

    def commit(self, transaction: object, *, command: CommitUpload,
               expected: ReadyUpload) -> CommittedUploadVersion:
        session = self._session(transaction)
        if command.project_id is not None:
            project = session.execute(select(ProjectRow).where(
                ProjectRow.project_id == command.project_id,
            ).with_for_update(of=ProjectRow)).scalar_one_or_none()
            if project is None or project.state != "ACTIVE":
                raise UploadCommitError("PROJECT_ARCHIVED")
        if expected.target_document_id is not None:
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == expected.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            ).with_for_update(of=DocumentRow)).scalar_one_or_none()
            self._check_document(document, command)
        intent = self._intent(session, command, lock=True)
        if intent is None:
            raise UploadCommitError("RESOURCE_NOT_FOUND")
        current = self._ready(session, transaction, intent, command)
        if current != expected:
            raise UploadCommitError("CONFLICT_STATE")
        self._file_publisher.publish(
            transaction,
            command=PublishFile(expected.file_object_id, command.scope,
                                command.project_id, command.actor_id,
                                command.trace_id, expected.file_lock_version,
                                command.max_bytes),
            expected=StagedFile(expected.staging_locator, expected.final_locator,
                                expected.sha256, expected.size_bytes),
        )
        if expected.target_document_id is None:
            document_id = uuid.uuid4()
            session.execute(insert(DocumentRow).values(
                document_id=document_id, scope=command.scope,
                project_id=command.project_id,
                document_category=intent.document_category,
                document_subtype=intent.document_subtype,
                document_purpose=intent.document_purpose,
                title=intent.title,
                original_display_name=intent.original_display_name,
                created_by=command.actor_id,
            ))
            document_version = 0
        else:
            document_id = expected.target_document_id
            document_version = command.expected_document_version
        version_id = self._version_writer.commit(
            transaction,
            command=CommitUploadVersion(
                document_id=document_id, file_object_id=expected.file_object_id,
                scope=command.scope, project_id=command.project_id,
                actor_id=command.actor_id, trace_id=command.trace_id,
                expected_document_version=document_version,
                max_bytes=command.max_bytes,
            ),
            expected=PublishedFileSnapshot(
                expected.final_locator, expected.sha256, expected.size_bytes,
                expected.detected_mime, expected.file_lock_version + 1,
            ),
        )
        version_no = session.execute(select(DocumentVersionRow.version_no).where(
            DocumentVersionRow.document_version_id == version_id,
        )).scalar_one()
        changed = session.execute(update(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.state == "CONTENT_READY",
            UploadIntentRow.lock_version == expected.intent_lock_version,
        ).values(
            state="COMMITTED", committed_document_id=document_id,
            document_version_id=version_id,
            lock_version=UploadIntentRow.lock_version + 1,
            updated_at=func.statement_timestamp(),
        ))
        if changed.rowcount != 1:
            raise UploadCommitError("CONFLICT_STATE")
        return CommittedUploadVersion(document_id, version_id, version_no)

    def replay(self, transaction: object, *, command: CommitUpload) -> CommittedUploadVersion:
        session = self._session(transaction)
        intent = self._intent(session, command, lock=False)
        if (intent is None or intent.state != "COMMITTED"
                or intent.committed_document_id is None
                or intent.document_version_id is None):
            raise UploadCommitError("CONFLICT_STATE")
        version = session.execute(select(DocumentVersionRow).where(
            DocumentVersionRow.document_version_id == intent.document_version_id,
            DocumentVersionRow.document_id == intent.committed_document_id,
            DocumentVersionRow.file_object_id == intent.file_object_id,
            DocumentVersionRow.scope == command.scope,
            DocumentVersionRow.project_id == command.project_id,
        )).scalar_one_or_none()
        if version is None:
            raise UploadCommitError("FILE_UNAVAILABLE")
        return CommittedUploadVersion(intent.committed_document_id,
                                      version.document_version_id, version.version_no)

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise UploadCommitError("DOCUMENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise UploadCommitError("DOCUMENT_UNAVAILABLE")
        return session

    @staticmethod
    def _intent(session: Session, command: CommitUpload, *, lock: bool):
        query = select(UploadIntentRow).where(
            UploadIntentRow.upload_id == command.upload_id,
            UploadIntentRow.scope == command.scope,
            UploadIntentRow.project_id == command.project_id,
            UploadIntentRow.actor_id == command.actor_id,
        )
        if lock:
            query = query.with_for_update(of=UploadIntentRow)
        return session.execute(query).scalar_one_or_none()

    def _ready(self, session: Session, transaction: object, intent,
               command: CommitUpload) -> ReadyUpload:
        if intent.state != "CONTENT_READY" or intent.file_object_id != command.upload_id:
            raise UploadCommitError("CONFLICT_STATE")
        if intent.expires_at <= session.execute(select(func.statement_timestamp())).scalar_one():
            raise UploadCommitError("FILE_UPLOAD_EXPIRED")
        if intent.original_display_name is None:
            raise UploadCommitError("CONFLICT_STATE")
        if intent.target_document_id is None:
            if command.expected_document_version is not None:
                raise UploadCommitError("VALIDATION_FAILED")
            if intent.document_category is None or intent.title is None:
                raise UploadCommitError("CONFLICT_STATE")
        else:
            if command.expected_document_version is None:
                raise UploadCommitError("PRECONDITION_REQUIRED")
            document = session.execute(select(DocumentRow).where(
                DocumentRow.document_id == intent.target_document_id,
                DocumentRow.scope == command.scope,
                DocumentRow.project_id == command.project_id,
            )).scalar_one_or_none()
            self._check_document(document, command)
        file = session.execute(select(FileObjectRow).where(
            FileObjectRow.file_object_id == intent.file_object_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        )).scalar_one_or_none()
        if (file is None or file.file_state != "STAGED"
                or file.storage_class != "PERSISTENT"
                or file.original_name_metadata != intent.original_display_name
                or type(file.sha256) is not bytes or len(file.sha256) != 32
                or type(file.size_bytes) is not int or not 0 <= file.size_bytes <= command.max_bytes
                or (intent.expected_size_bytes is not None
                    and file.size_bytes != intent.expected_size_bytes)
                or type(file.detected_mime) is not str or not file.detected_mime):
            raise UploadCommitError("FILE_UNAVAILABLE")
        try:
            stage, final = LocalFileStorage.locators(
                scope=command.scope, project_id=command.project_id,
                file_object_id=intent.file_object_id,
            )
        except LocalStorageError:
            raise UploadCommitError("FILE_UNAVAILABLE") from None
        if file.storage_locator != stage:
            raise UploadCommitError("FILE_UNAVAILABLE")
        return ReadyUpload(intent.file_object_id, stage, final,
                           file.sha256, file.size_bytes, file.detected_mime,
                           file.lock_version, intent.lock_version,
                           intent.target_document_id)

    @staticmethod
    def _check_document(document, command: CommitUpload) -> None:
        if document is None:
            raise UploadCommitError("RESOURCE_NOT_FOUND")
        if document.document_state != "ACTIVE" or document.document_category == "GENERATED_ARTIFACT":
            raise UploadCommitError("CONFLICT_STATE")
        if document.lock_version != command.expected_document_version:
            raise UploadCommitError("CONFLICT_VERSION")
