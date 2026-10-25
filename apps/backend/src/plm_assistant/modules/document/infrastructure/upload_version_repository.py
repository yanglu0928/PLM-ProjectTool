"""Document-owned upload version commit with locked pointer and file checks."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.commit_upload_version import (
    CommitUploadVersion, DocumentVersionCommitError, PublishedFileSnapshot,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, DocumentVersionSourceRefRow, FileObjectRow,
)
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyUploadVersionRepository:
    def prepared(self, transaction: object, *, command: CommitUploadVersion) -> PublishedFileSnapshot:
        session = self._session(transaction)
        document = self._document(session, command, lock=False)
        self._check_document(session, document, command, lock=False)
        file = self._file(session, command, lock=False)
        return self._snapshot(session, file, command)

    def commit(self, transaction: object, *, command: CommitUploadVersion,
               expected: PublishedFileSnapshot) -> uuid.UUID:
        session = self._session(transaction)
        # Keep this lock order stable for concurrent Project archival, document
        # commits and FileObject state changes.
        if command.project_id is not None:
            project = session.execute(select(ProjectRow).where(
                ProjectRow.project_id == command.project_id,
            ).with_for_update(of=ProjectRow)).scalar_one_or_none()
            if project is None or project.state != "ACTIVE":
                raise DocumentVersionCommitError("CONFLICT_STATE")
        document = self._document(session, command, lock=True)
        self._check_document(session, document, command, lock=True,
                             project_checked=True)
        file = self._file(session, command, lock=True)
        if self._snapshot(session, file, command) != expected:
            raise DocumentVersionCommitError("CONFLICT_VERSION")
        previous = None
        version_no = 1
        if document.latest_version_ref is not None:
            previous = session.execute(select(DocumentVersionRow).where(
                DocumentVersionRow.document_version_id == document.latest_version_ref,
                DocumentVersionRow.document_id == command.document_id,
            )).scalar_one_or_none()
            if previous is None:
                raise DocumentVersionCommitError("CONFLICT_STATE")
            version_no = previous.version_no + 1
        version_id = uuid.uuid4()
        session.execute(insert(DocumentVersionRow).values(
            document_version_id=version_id,
            document_id=command.document_id, scope=command.scope,
            project_id=command.project_id, version_no=version_no,
            file_object_id=command.file_object_id,
            content_sha256=expected.sha256, size_bytes=expected.size_bytes,
            detected_mime=expected.detected_mime,
            source_metadata={"source_kind": "UPLOAD"},
            created_by=command.actor_id, availability_state="AVAILABLE",
            supersedes_version_ref=(previous.document_version_id if previous else None),
            integrity_checked_at=func.statement_timestamp(),
        ))
        session.execute(insert(DocumentVersionSourceRefRow).values(
            source_ref_id=uuid.uuid4(), document_version_id=version_id,
            ordinal=0, source_kind="UPLOAD",
        ))
        changed = session.execute(update(DocumentRow).where(
            DocumentRow.document_id == command.document_id,
            DocumentRow.lock_version == command.expected_document_version,
            DocumentRow.document_state == "ACTIVE",
        ).values(
            latest_version_ref=version_id, updated_by=command.actor_id,
            updated_at=func.statement_timestamp(),
            lock_version=DocumentRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise DocumentVersionCommitError("CONFLICT_VERSION")
        return version_id

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE")
        return session

    @staticmethod
    def _document(session: Session, command: CommitUploadVersion, *, lock: bool):
        query = select(DocumentRow).where(
            DocumentRow.document_id == command.document_id,
            DocumentRow.scope == command.scope,
            DocumentRow.project_id == command.project_id,
        )
        if lock:
            query = query.with_for_update(of=DocumentRow)
        return session.execute(query).scalar_one_or_none()

    @staticmethod
    def _file(session: Session, command: CommitUploadVersion, *, lock: bool):
        query = select(FileObjectRow).where(
            FileObjectRow.file_object_id == command.file_object_id,
            FileObjectRow.scope == command.scope,
            FileObjectRow.project_id == command.project_id,
        )
        if lock:
            query = query.with_for_update(of=FileObjectRow)
        return session.execute(query).scalar_one_or_none()

    @staticmethod
    def _check_document(session: Session, document, command: CommitUploadVersion,
                        *, lock: bool, project_checked: bool = False) -> None:
        if document is None:
            raise DocumentVersionCommitError("RESOURCE_NOT_FOUND")
        if document.lock_version != command.expected_document_version:
            raise DocumentVersionCommitError("CONFLICT_VERSION")
        if document.document_state != "ACTIVE" or document.document_category == "GENERATED_ARTIFACT":
            raise DocumentVersionCommitError("CONFLICT_STATE")
        if command.project_id is not None and not project_checked:
            query = select(ProjectRow.state).where(ProjectRow.project_id == command.project_id)
            if lock:
                query = query.with_for_update(of=ProjectRow)
            if session.execute(query).scalar_one_or_none() != "ACTIVE":
                raise DocumentVersionCommitError("CONFLICT_STATE")

    @staticmethod
    def _snapshot(session: Session, file, command: CommitUploadVersion) -> PublishedFileSnapshot:
        if file is None:
            raise DocumentVersionCommitError("RESOURCE_NOT_FOUND")
        try:
            _, final = LocalFileStorage.locators(
                scope=command.scope, project_id=command.project_id,
                file_object_id=command.file_object_id,
            )
        except LocalStorageError:
            raise DocumentVersionCommitError("DOCUMENT_UNAVAILABLE") from None
        if (file.storage_class != "PERSISTENT" or file.file_state != "AVAILABLE"
                or file.storage_locator != final or file.available_at is None
                or type(file.sha256) is not bytes or len(file.sha256) != 32
                or type(file.size_bytes) is not int or file.size_bytes < 0
                or file.size_bytes > command.max_bytes
                or type(file.detected_mime) is not str or not file.detected_mime):
            raise DocumentVersionCommitError("CONFLICT_STATE")
        if session.execute(select(DocumentVersionRow.document_version_id).where(
            DocumentVersionRow.file_object_id == command.file_object_id,
        )).scalar_one_or_none() is not None:
            raise DocumentVersionCommitError("CONFLICT_STATE")
        return PublishedFileSnapshot(
            final, file.sha256, file.size_bytes, file.detected_mime, file.lock_version,
        )
