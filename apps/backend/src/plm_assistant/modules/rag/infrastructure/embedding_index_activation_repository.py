"""PostgreSQL owner for current-fact RAG index activation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.project.infrastructure.orm import ProjectMemberRow, ProjectRow
from plm_assistant.modules.rag.application.embedding_index_activation import (
    ActivatedRAGEmbeddingIndex,
    RAGEmbeddingIndexActivationError,
    RAGEmbeddingIndexActivationTarget,
)
from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingIndexActivationResultRow,
    EmbeddingIndexQualityResultRow,
    EmbeddingIndexRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active RAG activation transaction required")
    return session


class SqlAlchemyRAGEmbeddingIndexActivationRepository:
    def locked_target(
        self,
        transaction: object,
        *,
        embedding_index_id: uuid.UUID,
        actor_id: uuid.UUID,
        now: datetime,
    ) -> RAGEmbeddingIndexActivationTarget | None:
        if (
            any(type(value) is not uuid.UUID or not value.int for value in (
                embedding_index_id,
                actor_id,
            ))
            or not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise RAGEmbeddingIndexActivationError("VALIDATION_FAILED")
        session = _session(transaction)
        identity = session.scalar(select(EmbeddingIndexRow).where(
            EmbeddingIndexRow.embedding_index_id == embedding_index_id,
        ).execution_options(autoflush=False))
        if identity is None:
            return None
        indexes = session.scalars(
            select(EmbeddingIndexRow).where(
                EmbeddingIndexRow.scope == identity.scope,
                EmbeddingIndexRow.project_id.is_not_distinct_from(identity.project_id),
                EmbeddingIndexRow.index_purpose == identity.index_purpose,
            ).order_by(EmbeddingIndexRow.embedding_index_id)
            .with_for_update(of=EmbeddingIndexRow)
            .execution_options(autoflush=False, populate_existing=True)
        ).all()
        target = next((row for row in indexes
                       if row.embedding_index_id == embedding_index_id), None)
        if target is None:
            return None
        self._require_owner(session, target, actor_id)
        quality = session.scalar(select(EmbeddingIndexQualityResultRow).where(
            EmbeddingIndexQualityResultRow.embedding_index_id == embedding_index_id,
        ).order_by(
            EmbeddingIndexQualityResultRow.completed_at.desc(),
            EmbeddingIndexQualityResultRow.quality_result_id.desc(),
        ).limit(1).execution_options(autoflush=False))
        if quality is None:
            raise RAGEmbeddingIndexActivationError("RAG_INDEX_QUALITY_REQUIRED")
        active = next((row for row in indexes if row.index_state == "ACTIVE"), None)
        if target.index_state == "READY":
            if target.lock_version != 2 or quality.quality_state != "PASSED":
                raise RAGEmbeddingIndexActivationError(
                    "RAG_INDEX_ACTIVATION_PRECONDITION_FAILED",
                )
            self._require_current_facts(session, target, now)
        elif target.index_state != "ACTIVE" or target.lock_version != 3:
            raise RAGEmbeddingIndexActivationError("CONFLICT_VERSION")
        return RAGEmbeddingIndexActivationTarget(
            target.embedding_index_id,
            quality.quality_result_id,
            target.scope,
            target.project_id,
            target.index_purpose,
            target.index_state,
            target.lock_version,
            None if active is None or active.embedding_index_id == target.embedding_index_id
            else active.embedding_index_id,
            None if active is None or active.embedding_index_id == target.embedding_index_id
            else active.lock_version,
        )

    @staticmethod
    def _require_owner(session: Session, index: EmbeddingIndexRow,
                       actor_id: uuid.UUID) -> None:
        user = session.scalar(select(UserRow).where(
            UserRow.user_id == actor_id,
            UserRow.state == "ENABLED",
        ).execution_options(autoflush=False))
        if user is None:
            raise RAGEmbeddingIndexActivationError("AUTH_ACCESS_DENIED")
        if index.scope == "GLOBAL":
            if user.deployment_role != "DEPLOYMENT_ADMIN":
                raise RAGEmbeddingIndexActivationError("AUTH_ACCESS_DENIED")
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
            raise RAGEmbeddingIndexActivationError("AUTH_ACCESS_DENIED")

    @staticmethod
    def _require_current_facts(session: Session, index: EmbeddingIndexRow,
                               now: datetime) -> None:
        valid = session.execute(text("""
            SELECT
              EXISTS (SELECT 1 FROM plm.ai_models model
                WHERE model.ai_model_id=:model_id
                  AND model.model_kind='EMBEDDING'
                  AND model.embedding_dimension=:dimension
                  AND model.model_state='AVAILABLE'),
              EXISTS (SELECT 1 FROM plm.rag_embedding_builds build
                JOIN plm.rag_embedding_index_validations validation
                  ON validation.embedding_build_id=build.embedding_build_id
                 AND validation.embedding_index_id=build.embedding_index_id
                 AND validation.validation_state='PASSED'
                WHERE build.embedding_index_id=:index_id
                  AND build.build_state='SUCCEEDED'),
              NOT EXISTS (SELECT 1 FROM plm.rag_index_source_chunks source
                JOIN plm.rag_document_chunks chunk ON chunk.chunk_id=source.chunk_id
                WHERE source.embedding_index_id=:index_id
                  AND (chunk.chunk_state<>'ACTIVE'
                    OR chunk.text_fingerprint<>source.chunk_text_fingerprint
                    OR ROW(chunk.scope,chunk.project_id) IS DISTINCT FROM
                       ROW(:scope,CAST(:project_id AS uuid)))),
              NOT EXISTS (SELECT 1 FROM plm.rag_embedding_builds build
                JOIN plm.rag_embedding_build_batches batch
                  ON batch.embedding_build_id=build.embedding_build_id
                JOIN plm.ai_egress_authorizations authz
                  ON authz.authorization_id=batch.egress_authorization_ref
                WHERE build.embedding_index_id=:index_id
                  AND (authz.authorization_state<>'AUTHORIZED'
                    OR authz.valid_until<=:now
                    OR authz.ai_model_id<>:model_id
                    OR ROW(authz.scope,authz.project_id) IS DISTINCT FROM
                       ROW(:scope,CAST(:project_id AS uuid))))
        """), {
            "model_id": index.embedding_model_ref,
            "dimension": index.embedding_dimension,
            "index_id": index.embedding_index_id,
            "scope": index.scope,
            "project_id": index.project_id,
            "now": now,
        }).one()
        if valid != (True, True, True, True):
            raise RAGEmbeddingIndexActivationError(
                "RAG_INDEX_ACTIVATION_PRECONDITION_FAILED",
            )

    def activate(
        self,
        transaction: object,
        *,
        target: RAGEmbeddingIndexActivationTarget,
        actor_id: uuid.UUID,
        audit_event_id: uuid.UUID,
        trace_id: uuid.UUID,
    ) -> ActivatedRAGEmbeddingIndex:
        target.__post_init__()
        session = _session(transaction)
        audit = session.get(AuditEventRow, audit_event_id)
        index = session.get(EmbeddingIndexRow, target.embedding_index_id)
        retired = (None if target.retired_index_ref is None else
                   session.get(EmbeddingIndexRow, target.retired_index_ref))
        if audit is None or index is None or index.index_state != "READY" \
                or index.lock_version != 2:
            raise RAGEmbeddingIndexActivationError("CONFLICT_VERSION")
        if retired is not None:
            if (retired.index_state != "ACTIVE"
                    or retired.lock_version != target.retired_before_lock_version):
                raise RAGEmbeddingIndexActivationError("CONFLICT_VERSION")
            retired.index_state = "RETIRED"
            retired.lock_version += 1
            session.flush()
        index.index_state = "ACTIVE"
        index.lock_version = 3
        session.flush()
        row = EmbeddingIndexActivationResultRow(
            embedding_index_id=target.embedding_index_id,
            quality_result_ref=target.quality_result_ref,
            retired_index_ref=target.retired_index_ref,
            scope=target.scope,
            project_id=target.project_id,
            index_purpose=target.index_purpose,
            activated_by=actor_id,
            audit_event_id=audit_event_id,
            trace_id=trace_id,
            expected_lock_version=2,
            lock_version=3,
            retired_before_lock_version=target.retired_before_lock_version,
            retired_after_lock_version=(
                None if retired is None else retired.lock_version
            ),
            activated_at=audit.occurred_at,
        )
        session.add(row)
        session.flush()
        return self._result(row)

    def get(
        self,
        transaction: object,
        *,
        activation_result_id: uuid.UUID,
        embedding_index_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> ActivatedRAGEmbeddingIndex | None:
        if any(type(value) is not uuid.UUID or not value.int for value in (
            activation_result_id, embedding_index_id, actor_id,
        )):
            raise RAGEmbeddingIndexActivationError("VALIDATION_FAILED")
        session = _session(transaction)
        row = session.scalar(select(EmbeddingIndexActivationResultRow).where(
            EmbeddingIndexActivationResultRow.activation_result_id
            == activation_result_id,
            EmbeddingIndexActivationResultRow.embedding_index_id
            == embedding_index_id,
            EmbeddingIndexActivationResultRow.activated_by == actor_id,
        ).execution_options(autoflush=False))
        if row is None:
            return None
        audit = session.get(AuditEventRow, row.audit_event_id)
        if (
            audit is None
            or audit.trace_id != row.trace_id
            or audit.actor_type != "USER"
            or audit.actor_id != actor_id
            or audit.event_scope != (
                "DEPLOYMENT" if row.scope == "GLOBAL" else "PROJECT"
            )
            or audit.target_project_id != row.project_id
            or audit.action != "RAG_INDEX_ACTIVATED"
            or audit.outcome != "SUCCESS"
            or audit.target_owner_module != "rag"
            or audit.target_object_type != "RAG-03"
            or audit.target_object_id != embedding_index_id
            or audit.target_version_id != row.quality_result_ref
            or audit.before_state != "READY"
            or audit.after_state != "ACTIVE"
            or audit.occurred_at != row.activated_at
        ):
            raise RAGEmbeddingIndexActivationError()
        return self._result(row)

    @staticmethod
    def _result(row: EmbeddingIndexActivationResultRow) -> ActivatedRAGEmbeddingIndex:
        return ActivatedRAGEmbeddingIndex(
            row.activation_result_id,
            row.embedding_index_id,
            row.quality_result_ref,
            row.activated_by,
            row.audit_event_id,
            row.trace_id,
            row.scope,
            row.project_id,
            row.index_purpose,
            row.retired_index_ref,
            row.expected_lock_version,
            row.lock_version,
            row.retired_before_lock_version,
            row.retired_after_lock_version,
            row.activated_at,
        )
