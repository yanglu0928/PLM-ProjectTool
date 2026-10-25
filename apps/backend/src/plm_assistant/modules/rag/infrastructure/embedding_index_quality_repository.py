"""PostgreSQL owner for authorized immutable RAG quality evidence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.project.infrastructure.orm import (
    ProjectMemberRow,
    ProjectRow,
)
from plm_assistant.modules.rag.application.embedding_index_quality import (
    RAGEmbeddingIndexQualityError,
    RAGEmbeddingIndexQualityTarget,
    RecordedRAGEmbeddingIndexQuality,
    RegisterRAGEmbeddingIndexQuality,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingIndexQualityResultRow,
    EmbeddingIndexRow,
    EmbeddingIndexValidationRow,
)


_POLICY = "rag-business-quality-v1"


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active RAG quality transaction required")
    return session


class SqlAlchemyRAGEmbeddingIndexQualityRepository:
    def locked_target(
        self,
        transaction: object,
        *,
        embedding_index_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_lock_version: int,
    ) -> RAGEmbeddingIndexQualityTarget | None:
        if (
            any(type(value) is not uuid.UUID or not value.int for value in (
                embedding_index_id,
                actor_id,
            ))
            or expected_lock_version != 2
        ):
            raise RAGEmbeddingIndexQualityError("VALIDATION_FAILED")
        session = _session(transaction)
        index = session.scalar(
            select(EmbeddingIndexRow)
            .where(EmbeddingIndexRow.embedding_index_id == embedding_index_id)
            .with_for_update(of=EmbeddingIndexRow)
            .execution_options(autoflush=False)
        )
        if index is None:
            return None
        if index.index_state != "READY" or index.lock_version != expected_lock_version:
            raise RAGEmbeddingIndexQualityError("CONFLICT_VERSION")
        self._require_owner(session, index, actor_id)
        validation = session.scalar(
            select(EmbeddingIndexValidationRow).where(
                EmbeddingIndexValidationRow.embedding_index_id == embedding_index_id,
                EmbeddingIndexValidationRow.validation_state == "PASSED",
            ).execution_options(autoflush=False)
        )
        if (
            validation is None
            or validation.embedding_model_ref != index.embedding_model_ref
            or validation.source_snapshot_fingerprint
            != index.source_snapshot_fingerprint
        ):
            raise RAGEmbeddingIndexQualityError("RAG_INDEX_TECHNICAL_VALIDATION_REQUIRED")
        return RAGEmbeddingIndexQualityTarget(
            index.embedding_index_id,
            validation.embedding_index_validation_id,
            index.scope,
            index.project_id,
            index.index_purpose,
            index.embedding_model_ref,
            index.source_snapshot_fingerprint,
            index.index_state,
            index.lock_version,
        )

    @staticmethod
    def _require_owner(
        session: Session, index: EmbeddingIndexRow, actor_id: uuid.UUID,
    ) -> None:
        user = session.scalar(select(UserRow).where(
            UserRow.user_id == actor_id,
            UserRow.state == "ENABLED",
        ).execution_options(autoflush=False))
        if user is None:
            raise RAGEmbeddingIndexQualityError("AUTH_ACCESS_DENIED")
        if index.scope == "GLOBAL":
            if user.deployment_role != "DEPLOYMENT_ADMIN":
                raise RAGEmbeddingIndexQualityError("AUTH_ACCESS_DENIED")
            return
        project = session.scalar(select(ProjectRow).where(
            ProjectRow.project_id == index.project_id,
            ProjectRow.state == "ACTIVE",
        ).execution_options(autoflush=False))
        member = session.scalar(select(ProjectMemberRow).where(
            ProjectMemberRow.project_id == index.project_id,
            ProjectMemberRow.user_id == actor_id,
            ProjectMemberRow.state == "ACTIVE",
            ProjectMemberRow.project_role == "PROJECT_MANAGER",
        ).execution_options(autoflush=False))
        if project is None or member is None:
            raise RAGEmbeddingIndexQualityError("AUTH_ACCESS_DENIED")

    def save(
        self,
        transaction: object,
        *,
        target: RAGEmbeddingIndexQualityTarget,
        actor_id: uuid.UUID,
        command: RegisterRAGEmbeddingIndexQuality,
        classification_basis_points: int,
        exact_citation_basis_points: int,
        quality_state: str,
        error_code: str | None,
    ) -> RecordedRAGEmbeddingIndexQuality:
        target.__post_init__()
        session = _session(transaction)
        row = EmbeddingIndexQualityResultRow(
            embedding_index_id=target.embedding_index_id,
            technical_validation_ref=target.technical_validation_ref,
            scope=target.scope,
            project_id=target.project_id,
            index_purpose=target.index_purpose,
            embedding_model_ref=target.embedding_model_ref,
            source_snapshot_fingerprint=target.source_snapshot_fingerprint,
            dataset_ref=command.dataset_ref,
            dataset_fingerprint=command.dataset_fingerprint,
            isolation_attestation_fingerprint=
                command.isolation_attestation_fingerprint,
            evaluation_artifact_fingerprint=
                command.evaluation_artifact_fingerprint,
            evaluation_policy_ref=_POLICY,
            dataset_case_count=command.dataset_case_count,
            classification_correct_count=command.classification_correct_count,
            exact_citation_correct_count=command.exact_citation_correct_count,
            classification_basis_points=classification_basis_points,
            exact_citation_basis_points=exact_citation_basis_points,
            project_isolation_pass=command.project_isolation_pass,
            out_of_scope_citation_count=command.out_of_scope_citation_count,
            failure_closure_pass=command.failure_closure_pass,
            quality_state=quality_state,
            error_code=error_code,
            evaluated_by=actor_id,
            dataset_sealed_at=command.dataset_sealed_at,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return self._result(row)

    def get(
        self,
        transaction: object,
        *,
        quality_result_id: uuid.UUID,
        embedding_index_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> RecordedRAGEmbeddingIndexQuality | None:
        if any(type(value) is not uuid.UUID or not value.int for value in (
            quality_result_id,
            embedding_index_id,
            actor_id,
        )):
            raise RAGEmbeddingIndexQualityError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.scalar(select(EmbeddingIndexQualityResultRow).where(
            EmbeddingIndexQualityResultRow.quality_result_id == quality_result_id,
            EmbeddingIndexQualityResultRow.embedding_index_id == embedding_index_id,
            EmbeddingIndexQualityResultRow.evaluated_by == actor_id,
        ).execution_options(autoflush=False))
        if row is None:
            return None
        after = "QUALITY_PASSED" if row.quality_state == "PASSED" else "QUALITY_FAILED"
        audit = session.scalar(select(AuditEventRow).where(
            AuditEventRow.target_version_id == quality_result_id,
            AuditEventRow.target_object_id == embedding_index_id,
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.action == "RAG_INDEX_QUALITY_RECORDED",
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "rag",
            AuditEventRow.target_object_type == "RAG-03",
            AuditEventRow.before_state == "READY",
            AuditEventRow.after_state == after,
        ).execution_options(autoflush=False))
        if audit is None:
            raise RAGEmbeddingIndexQualityError()
        return self._result(row)

    @staticmethod
    def _result(row: EmbeddingIndexQualityResultRow) -> RecordedRAGEmbeddingIndexQuality:
        return RecordedRAGEmbeddingIndexQuality(
            row.quality_result_id,
            row.embedding_index_id,
            row.evaluated_by,
            row.dataset_ref,
            row.dataset_fingerprint,
            row.dataset_case_count,
            row.classification_correct_count,
            row.exact_citation_correct_count,
            row.classification_basis_points,
            row.exact_citation_basis_points,
            row.project_isolation_pass,
            row.out_of_scope_citation_count,
            row.failure_closure_pass,
            row.quality_state,
            row.error_code,
            row.completed_at,
        )
