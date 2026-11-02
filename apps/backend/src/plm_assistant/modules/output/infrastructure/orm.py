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
