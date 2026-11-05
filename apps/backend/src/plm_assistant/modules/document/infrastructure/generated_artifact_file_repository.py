"""PostgreSQL adapter for Output-specific SYSTEM file publication."""
from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.generated_artifact_file import (
    GeneratedFilePublicationError, GeneratedFileRequestFacts, GeneratedFileSnapshot,
)
from plm_assistant.modules.document.domain.file_state import (
    FileStateTransitionError, transition_requirements,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, FileObjectRow, FileStateEventRow,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.application.complete_generation import OutputArtifactPublication
from plm_assistant.modules.output.infrastructure.orm import OutputArtifactRow, OutputRequestRow
from plm_assistant.modules.plugin.infrastructure.orm import PluginExecutionRow


_MEDIA = {
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
}


class SqlAlchemyOutputGeneratedFilePublicationRepository:
    def lock_request(self, transaction: object, *, claim: ClaimedJob,
                     publication: OutputArtifactPublication) -> GeneratedFileRequestFacts:
        session = self._session(transaction)
        request_id = self._request_id(claim)
        snapshot_id = self._snapshot_id(claim)
        row = session.scalar(select(OutputRequestRow).where(
            OutputRequestRow.output_request_id == request_id,
            OutputRequestRow.project_id == claim.project_id,
            OutputRequestRow.job_ref == claim.job_id,
            OutputRequestRow.context_snapshot_id == snapshot_id,
            OutputRequestRow.current_execution_ref == publication.plugin_execution_id,
        ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True))
        if (row is None or row.output_type not in _MEDIA
                or _MEDIA[row.output_type] != publication.media_type
                or row.request_state not in {"GENERATING", "SUCCEEDED"}
                or (row.request_state == "GENERATING" and row.completed_at is not None)
                or (row.request_state == "SUCCEEDED" and row.completed_at is None)):
            raise GeneratedFilePublicationError()
        return GeneratedFileRequestFacts(
            row.output_request_id, row.project_id, row.job_ref,
            row.current_execution_ref, row.requested_by, row.trace_id,
            row.request_state, row.lock_version,
        )

    def snapshot(self, transaction: object, *, claim: ClaimedJob,
                 publication: OutputArtifactPublication,
                 request: GeneratedFileRequestFacts) -> GeneratedFileSnapshot:
        session = self._session(transaction)
        self._assert_current_request(session, claim, publication, request)
        execution = session.scalar(select(PluginExecutionRow).where(
            PluginExecutionRow.plugin_execution_id == publication.plugin_execution_id,
            PluginExecutionRow.project_id == claim.project_id,
            PluginExecutionRow.output_request_id == request.output_request_id,
            PluginExecutionRow.job_id == claim.job_id,
            PluginExecutionRow.attempt_no == claim.attempt_no,
            PluginExecutionRow.execution_state == "SUCCEEDED",
            PluginExecutionRow.result_manifest_ref.is_not(None),
            PluginExecutionRow.result_fingerprint.is_not(None),
        ).with_for_update(of=PluginExecutionRow))
        if execution is None:
            raise GeneratedFilePublicationError()
        try:
            stage, final = LocalFileStorage.locators(
                scope="PROJECT", project_id=claim.project_id,
                file_object_id=publication.file_object_id)
        except LocalStorageError:
            raise GeneratedFilePublicationError() from None
        file = session.scalar(select(FileObjectRow).where(
            FileObjectRow.file_object_id == publication.file_object_id,
            FileObjectRow.scope == "PROJECT", FileObjectRow.project_id == claim.project_id,
            FileObjectRow.usage_kind == "DOCUMENT", FileObjectRow.owner_object_id.is_(None),
            FileObjectRow.storage_class == "PERSISTENT",
            FileObjectRow.sha256 == publication.sha256,
            FileObjectRow.size_bytes == publication.size_bytes,
            FileObjectRow.detected_mime == publication.media_type,
        ).with_for_update(of=FileObjectRow))
        document = session.scalar(select(DocumentRow).where(
            DocumentRow.document_id == publication.document_id,
            DocumentRow.document_category == "GENERATED_ARTIFACT",
            DocumentRow.scope == "PROJECT", DocumentRow.project_id == claim.project_id,
            DocumentRow.document_state == "ACTIVE",
        ).with_for_update(of=DocumentRow).execution_options(populate_existing=True))
        if file is None or document is None:
            raise GeneratedFilePublicationError()
        self._validate_file_state(file, stage, final)
        if request.request_state == "SUCCEEDED":
            artifact_id = session.scalar(select(OutputArtifactRow.output_artifact_id).where(
                OutputArtifactRow.output_request_id == request.output_request_id,
                OutputArtifactRow.plugin_execution_id == publication.plugin_execution_id,
                OutputArtifactRow.project_id == claim.project_id,
            ).limit(1))
            if artifact_id is None or file.file_state != "AVAILABLE":
                raise GeneratedFilePublicationError()
        else:
            artifact_id = session.scalar(select(OutputArtifactRow.output_artifact_id).where(
                OutputArtifactRow.output_request_id == request.output_request_id,
                OutputArtifactRow.project_id == claim.project_id,
            ).limit(1))
            if artifact_id is not None:
                raise GeneratedFilePublicationError()
        return GeneratedFileSnapshot(
            request, document.document_id, file.file_object_id, file.file_state,
            file.lock_version, file.storage_locator, stage, final,
            file.sha256, file.size_bytes, file.detected_mime,
        )

    def mark_available(self, transaction: object, *, claim: ClaimedJob,
                       publication: OutputArtifactPublication,
                       expected: GeneratedFileSnapshot,
                       system_actor_id: uuid.UUID) -> GeneratedFileSnapshot:
        session = self._session(transaction)
        request = self.lock_request(
            transaction, claim=claim, publication=publication)
        if request.request_state != "GENERATING":
            raise GeneratedFilePublicationError()
        current = self.snapshot(
            transaction, claim=claim, publication=publication, request=request)
        if (current.request != expected.request
                or current.document_id != expected.document_id
                or current.file_object_id != expected.file_object_id
                or current.sha256 != expected.sha256
                or current.size_bytes != expected.size_bytes
                or current.media_type != expected.media_type
                or current.staging_locator != expected.staging_locator
                or current.final_locator != expected.final_locator):
            raise GeneratedFilePublicationError()
        if current.file_state == "AVAILABLE":
            if current.storage_locator != current.final_locator:
                raise GeneratedFilePublicationError()
            return current
        try:
            requirements = transition_requirements(
                from_state="STAGED", to_state="AVAILABLE",
                storage_class="PERSISTENT")
        except FileStateTransitionError:
            raise GeneratedFilePublicationError() from None
        if (not requirements.verify_final_content
                or current.storage_locator != current.staging_locator):
            raise GeneratedFilePublicationError()
        result = session.execute(update(FileObjectRow).where(
            FileObjectRow.file_object_id == current.file_object_id,
            FileObjectRow.scope == "PROJECT",
            FileObjectRow.project_id == claim.project_id,
            FileObjectRow.lock_version == current.file_lock_version,
            FileObjectRow.file_state == "STAGED",
            FileObjectRow.storage_locator == current.staging_locator,
            FileObjectRow.sha256 == publication.sha256,
            FileObjectRow.size_bytes == publication.size_bytes,
            FileObjectRow.detected_mime == publication.media_type,
            FileObjectRow.available_at.is_(None),
        ).values(
            file_state="AVAILABLE", storage_locator=current.final_locator,
            available_at=func.statement_timestamp(),
            updated_at=func.statement_timestamp(), updated_by=system_actor_id,
            lock_version=FileObjectRow.lock_version + 1,
        ))
        if result.rowcount != 1:
            raise GeneratedFilePublicationError()
        session.execute(insert(FileStateEventRow).values(
            file_object_id=current.file_object_id, from_state="STAGED",
            to_state="AVAILABLE", reason_code=None,
            actor_user_id=system_actor_id, trace_id=request.trace_id,
        ))
        return GeneratedFileSnapshot(
            request, current.document_id, current.file_object_id, "AVAILABLE",
            current.file_lock_version + 1, current.final_locator,
            current.staging_locator, current.final_locator, current.sha256,
            current.size_bytes, current.media_type)

    @staticmethod
    def _validate_file_state(file: FileObjectRow, stage: str, final: str) -> None:
        if file.file_state == "STAGED":
            if file.storage_locator != stage or file.available_at is not None:
                raise GeneratedFilePublicationError()
        elif file.file_state == "AVAILABLE":
            if file.storage_locator != final or file.available_at is None:
                raise GeneratedFilePublicationError()
        else:
            raise GeneratedFilePublicationError()

    @staticmethod
    def _assert_current_request(session: Session, claim: ClaimedJob,
                                publication: OutputArtifactPublication,
                                request: GeneratedFileRequestFacts) -> None:
        row = session.scalar(select(OutputRequestRow).where(
            OutputRequestRow.output_request_id == request.output_request_id,
            OutputRequestRow.project_id == claim.project_id,
            OutputRequestRow.job_ref == claim.job_id,
            OutputRequestRow.current_execution_ref == publication.plugin_execution_id,
        ))
        if (row is None or row.request_state != request.request_state
                or row.lock_version != request.request_lock_version):
            raise GeneratedFilePublicationError()

    @staticmethod
    def _request_id(claim: ClaimedJob) -> uuid.UUID:
        try:
            return uuid.UUID(claim.payload_refs["output_request_id"])
        except Exception:
            raise GeneratedFilePublicationError() from None

    @staticmethod
    def _snapshot_id(claim: ClaimedJob) -> uuid.UUID:
        try:
            return uuid.UUID(claim.payload_refs["context_snapshot_id"])
        except Exception:
            raise GeneratedFilePublicationError() from None

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise GeneratedFilePublicationError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise GeneratedFilePublicationError()
        return session
