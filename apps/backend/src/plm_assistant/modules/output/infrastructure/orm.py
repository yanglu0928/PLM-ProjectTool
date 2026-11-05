"""Closed Output request/context persistence foundations for OUT-01."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class OutputContextSnapshotRow(Base):
    """Immutable minimal, project-scoped context captured for one output request."""

    __tablename__ = "out_context_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "context_snapshot_id",
            "project_id",
            name="uq_out_context_snapshots__id_project",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_out_context_snapshots__project",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["plm.auth_users.user_id"],
            name="fk_out_context_snapshots__creator",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "jsonb_typeof(source_version_refs) = 'array' "
            "AND jsonb_array_length(source_version_refs) > 0",
            name="ck_out_context_snapshots__sources",
        ),
        CheckConstraint(
            "jsonb_typeof(context_payload) = 'object'",
            name="ck_out_context_snapshots__payload",
        ),
        CheckConstraint(
            "octet_length(context_fingerprint) = 32",
            name="ck_out_context_snapshots__fingerprint",
        ),
        CheckConstraint("isfinite(created_at)", name="ck_out_context_snapshots__created_at"),
        Index(
            "ix_out_context_snapshots__project_created",
            "project_id",
            "created_at",
            "context_snapshot_id",
        ),
        {"schema": "plm"},
    )

    context_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )


class OutputRequestRow(Base):
    """Closed OUT-01 request identity; application Owner is a later WBS."""

    __tablename__ = "out_output_requests"
    __table_args__ = (
        UniqueConstraint(
            "output_request_id",
            "project_id",
            name="uq_out_output_requests__id_project",
        ),
        UniqueConstraint(
            "output_request_id",
            "project_id",
            "output_type",
            name="uq_out_output_requests__id_project_type",
        ),
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_out_output_requests__project_idempotency",
        ),
        UniqueConstraint(
            "project_id",
            "output_type",
            "input_fingerprint",
            "template_version_ref",
            "output_policy_ref",
            "generation_no",
            name="uq_out_output_requests__generation_identity",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_out_output_requests__project",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["requested_by"],
            ["plm.auth_users.user_id"],
            name="fk_out_output_requests__requester",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["context_snapshot_id", "project_id"],
            [
                "plm.out_context_snapshots.context_snapshot_id",
                "plm.out_context_snapshots.project_id",
            ],
            name="fk_out_output_requests__context_project",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["job_ref"], ["plm.job_jobs.job_id"],
            name="fk_out_output_requests__job", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "output_type IN ('DOCX', 'PPTX', 'PNG', 'JPEG')",
            name="ck_out_output_requests__type",
        ),
        CheckConstraint(
            "request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING',"
            "'SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')",
            name="ck_out_output_requests__state",
        ),
        CheckConstraint(
            "jsonb_typeof(source_version_refs) = 'array' "
            "AND jsonb_array_length(source_version_refs) > 0",
            name="ck_out_output_requests__sources",
        ),
        CheckConstraint(
            "octet_length(input_fingerprint) = 32",
            name="ck_out_output_requests__fingerprint",
        ),
        CheckConstraint(
            "generation_no > 0 AND lock_version >= 0",
            name="ck_out_output_requests__generation_lock",
        ),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 200 "
            "AND idempotency_key = btrim(idempotency_key)",
            name="ck_out_output_requests__idempotency",
        ),
        CheckConstraint(
            "char_length(output_policy_ref) BETWEEN 1 AND 200 "
            "AND output_policy_ref = btrim(output_policy_ref)",
            name="ck_out_output_requests__policy",
        ),
        CheckConstraint(
            "char_length(plugin_operation) BETWEEN 1 AND 200 "
            "AND plugin_operation = btrim(plugin_operation)",
            name="ck_out_output_requests__plugin_operation",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_out_output_requests__completed_at",
        ),
        Index(
            "ix_out_output_requests__project_state_requested",
            "project_id",
            "request_state",
            "requested_at",
            "output_request_id",
        ),
        {"schema": "plm"},
    )

    output_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    template_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    plugin_operation: Mapped[str] = mapped_column(Text, nullable=False)
    context_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    generation_no: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    request_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'REQUESTED'")
    )
    job_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    current_execution_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class OutputArtifactRow(Base):
    """Closed OUT-02 artifact reference; this table stores metadata, never bytes."""
    __tablename__ = "out_artifacts"
    __table_args__ = (
        UniqueConstraint("output_artifact_id", "project_id",
                         name="uq_out_artifacts__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_out_artifacts__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["output_request_id", "project_id", "artifact_kind"],
            ["plm.out_output_requests.output_request_id",
             "plm.out_output_requests.project_id", "plm.out_output_requests.output_type"],
            name="fk_out_artifacts__request_kind_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["plugin_execution_id", "output_request_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id",
             "plm.plg_executions.output_request_id", "plm.plg_executions.project_id"],
            name="fk_out_artifacts__execution_request_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["document_id", "document_category", "scope", "project_id"],
            ["plm.doc_documents.document_id", "plm.doc_documents.document_category",
             "plm.doc_documents.scope", "plm.doc_documents.project_id"],
            name="fk_out_artifacts__generated_document_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["document_version_id", "document_id", "scope", "project_id",
             "file_object_id", "artifact_sha256", "size_bytes", "media_type"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id", "plm.doc_document_versions.scope",
             "plm.doc_document_versions.project_id", "plm.doc_document_versions.file_object_id",
             "plm.doc_document_versions.content_sha256", "plm.doc_document_versions.size_bytes",
             "plm.doc_document_versions.detected_mime"],
            name="fk_out_artifacts__document_version_content", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["file_object_id", "scope", "project_id", "artifact_sha256",
             "size_bytes", "media_type"],
            ["plm.doc_file_objects.file_object_id", "plm.doc_file_objects.scope",
             "plm.doc_file_objects.project_id", "plm.doc_file_objects.sha256",
             "plm.doc_file_objects.size_bytes", "plm.doc_file_objects.detected_mime"],
            name="fk_out_artifacts__file_content_project", ondelete="NO ACTION"),
        CheckConstraint("scope='PROJECT' AND document_category='GENERATED_ARTIFACT'",
                        name="ck_out_artifacts__project_generated_document"),
        CheckConstraint("artifact_kind IN ('DOCX','PPTX','PNG','JPEG')",
                        name="ck_out_artifacts__kind"),
        CheckConstraint(
            "(artifact_kind='DOCX' AND media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document') OR "
            "(artifact_kind='PPTX' AND media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation') OR "
            "(artifact_kind='PNG' AND media_type='image/png') OR "
            "(artifact_kind='JPEG' AND media_type='image/jpeg')",
            name="ck_out_artifacts__kind_media_type"),
        CheckConstraint("artifact_state IN ('VALIDATING','AVAILABLE','RESTRICTED','REVOKED')",
                        name="ck_out_artifacts__state"),
        CheckConstraint(
            "(artifact_state='VALIDATING' AND published_at IS NULL) OR "
            "(artifact_state='AVAILABLE' AND published_at IS NOT NULL) OR "
            "artifact_state IN ('RESTRICTED','REVOKED')",
            name="ck_out_artifacts__publish_time"),
        CheckConstraint(
            "artifact_state <> 'AVAILABLE' OR "
            "(validation_summary->>'format_code' IS NOT DISTINCT FROM 'PASSED' "
            "AND validation_summary->>'structure_code' IS NOT DISTINCT FROM 'PASSED' "
            "AND validation_summary->>'hash_code' IS NOT DISTINCT FROM 'PASSED' "
            "AND validation_summary->>'content_code' IS NOT DISTINCT FROM 'PASSED')",
            name="ck_out_artifacts__available_validated",
        ),
        CheckConstraint("octet_length(artifact_sha256)=32",
                        name="ck_out_artifacts__sha256"),
        CheckConstraint("size_bytes BETWEEN 0 AND 134217728",
                        name="ck_out_artifacts__size"),
        CheckConstraint(
            "jsonb_typeof(validation_summary)='object' "
            "AND validation_summary - ARRAY['format_code','structure_code','hash_code','content_code'] = '{}'::jsonb "
            "AND (NOT (validation_summary ? 'format_code') OR validation_summary->>'format_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'structure_code') OR validation_summary->>'structure_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'hash_code') OR validation_summary->>'hash_code' ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (NOT (validation_summary ? 'content_code') OR validation_summary->>'content_code' ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_out_artifacts__validation_summary_codes"),
        CheckConstraint("lock_version >= 0 AND isfinite(created_at) "
                        "AND (published_at IS NULL OR isfinite(published_at))",
                        name="ck_out_artifacts__time_lock"),
        Index("ix_out_artifacts__project_state_created",
              "project_id", "artifact_state", "created_at", "output_artifact_id"),
        {"schema": "plm"},
    )
    output_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_category: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'GENERATED_ARTIFACT'"))
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PROJECT'"))
    artifact_kind: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    artifact_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'VALIDATING'"))
    validation_summary: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6))
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"))


class OutputArtifactValidationResultRow(Base):
    """Append-only, code-only validation evidence for one project artifact."""
    __tablename__ = "out_artifact_validation_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["output_artifact_id", "project_id"],
            ["plm.out_artifacts.output_artifact_id", "plm.out_artifacts.project_id"],
            name="fk_out_artifact_validation__artifact_project", ondelete="NO ACTION"),
        CheckConstraint("validation_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                        name="ck_out_artifact_validation__code"),
        CheckConstraint("validation_state IN ('PASSED','FAILED','WARNING')",
                        name="ck_out_artifact_validation__state"),
        CheckConstraint("evidence_fingerprint IS NULL OR octet_length(evidence_fingerprint)=32",
                        name="ck_out_artifact_validation__fingerprint"),
        CheckConstraint("isfinite(checked_at)",
                        name="ck_out_artifact_validation__checked_at"),
        Index("ix_out_artifact_validation__artifact_time",
              "output_artifact_id", "project_id", "checked_at", "validation_result_id"),
        {"schema": "plm"},
    )
    validation_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    output_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    validation_code: Mapped[str] = mapped_column(Text, nullable=False)
    validation_state: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
