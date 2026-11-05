"""PostgreSQL adapter for the internal Output-generated DocumentVersion owner."""
from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.generated_artifact_version import (
    GeneratedDocumentVersion, GeneratedVersionError, GeneratedVersionFacts,
)
from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError,
)
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, DocumentVersionSourceRefRow, FileObjectRow,
)
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.output.infrastructure.orm import OutputArtifactRow, OutputRequestRow
from plm_assistant.modules.plugin.infrastructure.orm import PluginExecutionRow
from plm_assistant.modules.project.infrastructure.orm import ProjectRow


class SqlAlchemyOutputGeneratedDocumentVersionRepository:
    def lock_request(self, transaction: object, *, claim: ClaimedJob,
                     execution_id: uuid.UUID, publication: GeneratedDocumentVersion) -> bool:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        row = session.scalar(select(OutputRequestRow).where(
            OutputRequestRow.output_request_id == request_id,
            OutputRequestRow.project_id == claim.project_id,
            OutputRequestRow.job_ref == claim.job_id,
            OutputRequestRow.context_snapshot_id == snapshot_id,
            OutputRequestRow.current_execution_ref == execution_id,
            OutputRequestRow.request_state == "GENERATING",
            OutputRequestRow.completed_at.is_(None),
        ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True))
        if row is None:
            return False
        expected_media = {
            "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "PNG": "image/png", "JPEG": "image/jpeg",
        }.get(row.output_type)
        return expected_media is not None and expected_media == publication.media_type

    def commit_generated_version(
        self, transaction: object, *, claim: ClaimedJob, execution_id: uuid.UUID,
        system_actor_id: uuid.UUID, publication: GeneratedDocumentVersion,
    ) -> GeneratedVersionFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        request = session.scalar(select(OutputRequestRow).where(
            OutputRequestRow.output_request_id == request_id,
            OutputRequestRow.project_id == claim.project_id,
            OutputRequestRow.job_ref == claim.job_id,
            OutputRequestRow.context_snapshot_id == snapshot_id,
            OutputRequestRow.current_execution_ref == execution_id,
            OutputRequestRow.request_state == "GENERATING",
            OutputRequestRow.completed_at.is_(None),
        ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True))
        if request is None or request.output_type not in {
            "DOCX", "PPTX", "PNG", "JPEG",
        }:
            raise GeneratedVersionError()
        if publication.media_type != {
            "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "PNG": "image/png", "JPEG": "image/jpeg",
        }[request.output_type]:
            raise GeneratedVersionError()

        project = session.scalar(select(ProjectRow).where(
            ProjectRow.project_id == claim.project_id,
            ProjectRow.state == "ACTIVE",
        ))
        execution = session.scalar(select(PluginExecutionRow).where(
            PluginExecutionRow.plugin_execution_id == execution_id,
            PluginExecutionRow.output_request_id == request_id,
            PluginExecutionRow.project_id == claim.project_id,
            PluginExecutionRow.job_id == claim.job_id,
            PluginExecutionRow.attempt_no == claim.attempt_no,
            PluginExecutionRow.execution_state == "SUCCEEDED",
            PluginExecutionRow.result_manifest_ref.is_not(None),
            PluginExecutionRow.result_fingerprint.is_not(None),
        ).with_for_update(of=PluginExecutionRow))
        if project is None or execution is None:
            raise GeneratedVersionError()

        try:
            stage, final = LocalFileStorage.locators(
                scope="PROJECT", project_id=claim.project_id,
                file_object_id=publication.file_object_id)
        except LocalStorageError:
            raise GeneratedVersionError() from None
        file_object = session.scalar(select(FileObjectRow).where(
            FileObjectRow.file_object_id == publication.file_object_id,
            FileObjectRow.scope == "PROJECT",
            FileObjectRow.project_id == claim.project_id,
            FileObjectRow.usage_kind == "DOCUMENT",
            FileObjectRow.owner_object_id.is_(None),
            FileObjectRow.storage_class == "PERSISTENT",
            FileObjectRow.file_state == "AVAILABLE",
            FileObjectRow.storage_locator == final,
            FileObjectRow.sha256 == publication.sha256,
            FileObjectRow.size_bytes == publication.size_bytes,
            FileObjectRow.detected_mime == publication.media_type,
            FileObjectRow.available_at.is_not(None),
        ).with_for_update(of=FileObjectRow))
        document = session.scalar(select(DocumentRow).where(
            DocumentRow.document_id == publication.document_id,
            DocumentRow.document_category == "GENERATED_ARTIFACT",
            DocumentRow.scope == "PROJECT",
            DocumentRow.project_id == claim.project_id,
            DocumentRow.document_state == "ACTIVE",
        ).with_for_update(of=DocumentRow).execution_options(populate_existing=True))
        if file_object is None or document is None:
            raise GeneratedVersionError()

        existing = session.scalar(select(DocumentVersionRow).where(
            DocumentVersionRow.file_object_id == publication.file_object_id,
        ).with_for_update(of=DocumentVersionRow))
        if existing is not None:
            source = session.scalar(select(DocumentVersionSourceRefRow).where(
                DocumentVersionSourceRefRow.document_version_id == existing.document_version_id,
                DocumentVersionSourceRefRow.ordinal == 0,
                DocumentVersionSourceRefRow.source_kind == "OUTPUT_GENERATION",
                DocumentVersionSourceRefRow.source_owner_module == "output",
                DocumentVersionSourceRefRow.source_object_type == "OUT-01",
                DocumentVersionSourceRefRow.source_object_id == request_id,
                DocumentVersionSourceRefRow.source_version_id == execution_id,
            ))
            if (source is None or existing.document_version_id != publication.document_version_id
                    or existing.document_id != document.document_id
                    or existing.scope != "PROJECT" or existing.project_id != claim.project_id
                    or existing.content_sha256 != publication.sha256
                    or existing.size_bytes != publication.size_bytes
                    or existing.detected_mime != publication.media_type
                    or existing.availability_state != "AVAILABLE"
                    or document.latest_version_ref != existing.document_version_id):
                raise GeneratedVersionError()
            return GeneratedVersionFacts(
                request_id, claim.project_id, document.document_id,
                existing.document_version_id, publication.file_object_id,
                execution_id, existing.version_no, False)

        artifact = session.scalar(select(OutputArtifactRow.output_artifact_id).where(
            OutputArtifactRow.output_request_id == request_id,
            OutputArtifactRow.project_id == claim.project_id,
        ).limit(1))
        if artifact is not None or document.latest_version_ref is None and session.scalar(
            select(DocumentVersionRow.document_version_id).where(
                DocumentVersionRow.document_id == document.document_id).limit(1)
        ) is not None:
            raise GeneratedVersionError()

        latest = session.scalar(select(DocumentVersionRow).where(
            DocumentVersionRow.document_id == document.document_id,
        ).order_by(DocumentVersionRow.version_no.desc()).limit(1))
        if ((latest is None and (document.latest_version_ref is not None))
                or (latest is not None and document.latest_version_ref != latest.document_version_id)):
            raise GeneratedVersionError()
        version_no = 1 if latest is None else latest.version_no + 1
        supersedes = None if latest is None else latest.document_version_id
        if session.scalar(select(ProjectRow.project_id).where(
            ProjectRow.project_id == claim.project_id,
            ProjectRow.state == "ACTIVE",
        )) is None:
            raise GeneratedVersionError()
        source_metadata = {
            "source_kind": "OUTPUT_GENERATION",
            "output_request_id": str(request_id),
            "plugin_execution_id": str(execution_id),
            "job_id": str(claim.job_id),
            "attempt_no": claim.attempt_no,
            "fencing_token": claim.fencing_token,
            "output_type": request.output_type,
        }
        session.execute(insert(DocumentVersionRow).values(
            document_version_id=publication.document_version_id,
            document_id=document.document_id, scope="PROJECT",
            project_id=claim.project_id, version_no=version_no,
            file_object_id=publication.file_object_id,
            content_sha256=publication.sha256, size_bytes=publication.size_bytes,
            detected_mime=publication.media_type, source_metadata=source_metadata,
            created_by=system_actor_id, availability_state="AVAILABLE",
            supersedes_version_ref=supersedes,
        ))
        session.execute(insert(DocumentVersionSourceRefRow).values(
            source_ref_id=uuid.uuid5(publication.document_version_id, "output-source-ref"),
            document_version_id=publication.document_version_id, ordinal=0,
            source_kind="OUTPUT_GENERATION", source_owner_module="output",
            source_object_type="OUT-01", source_object_id=request_id,
            source_version_id=execution_id,
        ))
        changed = session.execute(update(DocumentRow).where(
            DocumentRow.document_id == document.document_id,
            DocumentRow.lock_version == document.lock_version,
            DocumentRow.latest_version_ref == document.latest_version_ref,
        ).values(
            latest_version_ref=publication.document_version_id,
            updated_by=system_actor_id,
            updated_at=func.statement_timestamp(),
            lock_version=DocumentRow.lock_version + 1,
        ))
        if changed.rowcount != 1:
            raise GeneratedVersionError()
        return GeneratedVersionFacts(
            request_id, claim.project_id, document.document_id,
            publication.document_version_id, publication.file_object_id,
            execution_id, version_no, True)

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise GeneratedVersionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise GeneratedVersionError()
        return session
