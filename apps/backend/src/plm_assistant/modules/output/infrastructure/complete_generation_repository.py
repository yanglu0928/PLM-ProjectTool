"""PostgreSQL persistence for Output generation success finalization."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.document.infrastructure.orm import (
    DocumentRow, DocumentVersionRow, FileObjectRow,
)
from plm_assistant.modules.output.application.complete_generation import (
    OutputArtifactPublication, OutputGenerationCompletionError,
    OutputGenerationCompletionFacts,
)
from plm_assistant.modules.output.infrastructure.orm import (
    OutputArtifactRow, OutputArtifactValidationResultRow, OutputRequestRow,
)
from plm_assistant.modules.plugin.infrastructure.orm import PluginExecutionRow


class SqlAlchemyOutputGenerationCompletionRepository:
    def lock_candidate(self, transaction: object, *, claim: ClaimedJob,
                       execution_id: uuid.UUID) -> OutputGenerationCompletionFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        row = session.scalar(
            select(OutputRequestRow).where(
                OutputRequestRow.output_request_id == request_id,
                OutputRequestRow.project_id == claim.project_id,
                OutputRequestRow.job_ref == claim.job_id,
                OutputRequestRow.context_snapshot_id == snapshot_id,
            ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True)
        )
        if (row is None or row.current_execution_ref != execution_id):
            raise OutputGenerationCompletionError()
        if row.request_state == "GENERATING" and row.completed_at is None:
            existing = session.scalar(select(OutputArtifactRow.output_artifact_id).where(
                OutputArtifactRow.plugin_execution_id == execution_id,
                OutputArtifactRow.project_id == claim.project_id,
            ).limit(1))
            if existing is not None:
                raise OutputGenerationCompletionError()
            return self._facts(
                artifact_id=None, row=row, execution_id=execution_id, changed=False,
            )
        if row.request_state != "SUCCEEDED" or row.completed_at is None:
            raise OutputGenerationCompletionError()
        artifact = session.scalar(select(OutputArtifactRow).where(
            OutputArtifactRow.output_request_id == request_id,
            OutputArtifactRow.plugin_execution_id == execution_id,
            OutputArtifactRow.project_id == claim.project_id,
        ).with_for_update(of=OutputArtifactRow))
        if artifact is None or artifact.artifact_state != "AVAILABLE":
            raise OutputGenerationCompletionError()
        return self._facts(
            artifact_id=artifact.output_artifact_id, row=row,
            execution_id=execution_id, changed=False,
        )

    def verify_completed_generation(
            self, transaction: object, *, claim: ClaimedJob,
            execution_id: uuid.UUID, publication: OutputArtifactPublication
    ) -> OutputGenerationCompletionFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        request = session.scalar(select(OutputRequestRow).where(
            OutputRequestRow.output_request_id == request_id,
            OutputRequestRow.project_id == claim.project_id,
            OutputRequestRow.job_ref == claim.job_id,
            OutputRequestRow.context_snapshot_id == snapshot_id,
        ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True))
        if (request is None or request.request_state != "SUCCEEDED"
                or request.current_execution_ref != execution_id
                or request.completed_at is None
                or request.output_type not in {"DOCX", "PPTX", "PNG", "JPEG"}
                or publication.media_type != {
                    "DOCX":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "PPTX":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "PNG":"image/png","JPEG":"image/jpeg",
                }[request.output_type]):
            raise OutputGenerationCompletionError()
        execution = session.scalar(select(PluginExecutionRow).where(
            PluginExecutionRow.plugin_execution_id == execution_id,
            PluginExecutionRow.output_request_id == request_id,
            PluginExecutionRow.project_id == claim.project_id,
            PluginExecutionRow.job_id == claim.job_id,
            PluginExecutionRow.attempt_no == claim.attempt_no,
            PluginExecutionRow.execution_state == "SUCCEEDED",
            PluginExecutionRow.result_manifest_ref.is_not(None),
            PluginExecutionRow.result_fingerprint.is_not(None),
        ))
        if execution is None:
            raise OutputGenerationCompletionError()
        artifact = session.scalar(select(OutputArtifactRow).where(
            OutputArtifactRow.output_artifact_id == publication.artifact_id,
            OutputArtifactRow.project_id == claim.project_id,
            OutputArtifactRow.output_request_id == request_id,
            OutputArtifactRow.plugin_execution_id == execution_id,
            OutputArtifactRow.document_id == publication.document_id,
            OutputArtifactRow.document_version_id == publication.document_version_id,
            OutputArtifactRow.file_object_id == publication.file_object_id,
            OutputArtifactRow.artifact_kind == request.output_type,
            OutputArtifactRow.media_type == publication.media_type,
            OutputArtifactRow.artifact_sha256 == publication.sha256,
            OutputArtifactRow.size_bytes == publication.size_bytes,
            OutputArtifactRow.artifact_state == "AVAILABLE",
        ).with_for_update(of=OutputArtifactRow))
        if (artifact is None or artifact.published_at is None
                or artifact.validation_summary != {
                    "format_code":"PASSED", "structure_code":"PASSED",
                    "hash_code":"PASSED", "content_code":"PASSED",
                }):
            raise OutputGenerationCompletionError()
        file_object = session.scalar(select(FileObjectRow).where(
            FileObjectRow.file_object_id == publication.file_object_id,
            FileObjectRow.scope == "PROJECT", FileObjectRow.project_id == claim.project_id,
            FileObjectRow.file_state == "AVAILABLE", FileObjectRow.sha256 == publication.sha256,
            FileObjectRow.size_bytes == publication.size_bytes,
            FileObjectRow.detected_mime == publication.media_type,
        ))
        document = session.scalar(select(DocumentRow).where(
            DocumentRow.document_id == publication.document_id,
            DocumentRow.document_category == "GENERATED_ARTIFACT",
            DocumentRow.scope == "PROJECT", DocumentRow.project_id == claim.project_id,
            DocumentRow.document_state == "ACTIVE",
        ))
        version = session.scalar(select(DocumentVersionRow).where(
            DocumentVersionRow.document_version_id == publication.document_version_id,
            DocumentVersionRow.document_id == publication.document_id,
            DocumentVersionRow.scope == "PROJECT", DocumentVersionRow.project_id == claim.project_id,
            DocumentVersionRow.file_object_id == publication.file_object_id,
            DocumentVersionRow.content_sha256 == publication.sha256,
            DocumentVersionRow.size_bytes == publication.size_bytes,
            DocumentVersionRow.detected_mime == publication.media_type,
            DocumentVersionRow.availability_state == "AVAILABLE",
        ))
        if file_object is None or document is None or version is None:
            raise OutputGenerationCompletionError()
        saved = session.scalars(select(OutputArtifactValidationResultRow).where(
            OutputArtifactValidationResultRow.output_artifact_id == publication.artifact_id,
            OutputArtifactValidationResultRow.project_id == claim.project_id,
        )).all()
        expected = sorted(
            (item.code, item.state, item.evidence_fingerprint)
            for item in publication.validations
        )
        actual = sorted(
            (item.validation_code, item.validation_state, item.evidence_fingerprint)
            for item in saved
        )
        if actual != expected:
            raise OutputGenerationCompletionError()
        return self._facts(
            artifact_id=publication.artifact_id, row=request,
            execution_id=execution_id, changed=False,
        )

    def complete_generation(self, transaction: object, *, claim: ClaimedJob,
                            execution_id: uuid.UUID, expected_lock_version: int,
                            publication: OutputArtifactPublication
                            ) -> OutputGenerationCompletionFacts:
        session = self._session(transaction)
        request_id = uuid.UUID(claim.payload_refs["output_request_id"])
        snapshot_id = uuid.UUID(claim.payload_refs["context_snapshot_id"])
        request = session.scalar(
            select(OutputRequestRow).where(
                OutputRequestRow.output_request_id == request_id,
                OutputRequestRow.project_id == claim.project_id,
                OutputRequestRow.job_ref == claim.job_id,
                OutputRequestRow.context_snapshot_id == snapshot_id,
            ).with_for_update(of=OutputRequestRow).execution_options(populate_existing=True)
        )
        if (request is None or request.request_state != "GENERATING"
                or request.current_execution_ref != execution_id
                or request.completed_at is not None or request.lock_version != expected_lock_version
                or request.output_type not in {"DOCX", "PPTX", "PNG", "JPEG"}):
            raise OutputGenerationCompletionError()
        if publication.media_type != {
            "DOCX":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "PPTX":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "PNG":"image/png","JPEG":"image/jpeg",
        }[request.output_type]:
            raise OutputGenerationCompletionError()
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
        if execution is None:
            raise OutputGenerationCompletionError()

        file_object = session.scalar(select(FileObjectRow).where(
            FileObjectRow.file_object_id == publication.file_object_id,
            FileObjectRow.scope == "PROJECT",
            FileObjectRow.project_id == claim.project_id,
            FileObjectRow.file_state == "AVAILABLE",
            FileObjectRow.sha256 == publication.sha256,
            FileObjectRow.size_bytes == publication.size_bytes,
            FileObjectRow.detected_mime == publication.media_type,
        ).with_for_update(of=FileObjectRow))
        document = session.scalar(select(DocumentRow).where(
            DocumentRow.document_id == publication.document_id,
            DocumentRow.document_category == "GENERATED_ARTIFACT",
            DocumentRow.scope == "PROJECT",
            DocumentRow.project_id == claim.project_id,
            DocumentRow.document_state == "ACTIVE",
        ).with_for_update(of=DocumentRow))
        version = session.scalar(select(DocumentVersionRow).where(
            DocumentVersionRow.document_version_id == publication.document_version_id,
            DocumentVersionRow.document_id == publication.document_id,
            DocumentVersionRow.scope == "PROJECT",
            DocumentVersionRow.project_id == claim.project_id,
            DocumentVersionRow.file_object_id == publication.file_object_id,
            DocumentVersionRow.content_sha256 == publication.sha256,
            DocumentVersionRow.size_bytes == publication.size_bytes,
            DocumentVersionRow.detected_mime == publication.media_type,
            DocumentVersionRow.availability_state == "AVAILABLE",
        ).with_for_update(of=DocumentVersionRow))
        if file_object is None or document is None or version is None:
            raise OutputGenerationCompletionError()

        summary = {
            "format_code":"PASSED", "structure_code":"PASSED",
            "hash_code":"PASSED", "content_code":"PASSED",
        }
        session.execute(text("SET LOCAL plm.output_artifact_owner_write='on'"))
        artifact = OutputArtifactRow(
            output_artifact_id=publication.artifact_id,
            project_id=claim.project_id,
            output_request_id=request_id,
            plugin_execution_id=execution_id,
            document_id=publication.document_id,
            document_version_id=publication.document_version_id,
            file_object_id=publication.file_object_id,
            document_category="GENERATED_ARTIFACT",
            scope="PROJECT",
            artifact_kind=request.output_type,
            media_type=publication.media_type,
            artifact_sha256=publication.sha256,
            size_bytes=publication.size_bytes,
            artifact_state="VALIDATING",
            validation_summary=summary,
        )
        session.add(artifact)
        session.flush()
        for evidence in publication.validations:
            session.add(OutputArtifactValidationResultRow(
                validation_result_id=uuid.uuid4(),
                output_artifact_id=publication.artifact_id,
                project_id=claim.project_id,
                validation_code=evidence.code,
                validation_state=evidence.state,
                evidence_fingerprint=evidence.evidence_fingerprint,
            ))
        session.flush()
        now = session.scalar(select(func.statement_timestamp()))
        artifact.artifact_state = "AVAILABLE"
        artifact.published_at = now
        artifact.lock_version += 1
        request.request_state = "SUCCEEDED"
        request.completed_at = now
        request.lock_version += 1
        session.flush()
        return self._facts(
            artifact_id=publication.artifact_id, row=request,
            execution_id=execution_id, changed=True,
        )

    @staticmethod
    def _facts(artifact_id: uuid.UUID | None, row: OutputRequestRow,
               execution_id: uuid.UUID, *, changed: bool) -> OutputGenerationCompletionFacts:
        return OutputGenerationCompletionFacts(
            artifact_id, row.output_request_id, row.project_id,
            row.job_ref, row.context_snapshot_id, row.requested_by, execution_id,
            row.output_type, row.request_state, "MISSING" if artifact_id is None else "AVAILABLE",
            row.lock_version, changed,
        )

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session
        except (AttributeError, RuntimeError):
            raise OutputGenerationCompletionError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise OutputGenerationCompletionError()
        return session
