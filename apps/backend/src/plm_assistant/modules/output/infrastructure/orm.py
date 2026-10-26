"""OUT-01 OutputRequest and immutable OutputContext persistence schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import LargeBinary

from plm_assistant.modules.platform.infrastructure.orm import Base


_LIVE_STATES = "'REQUESTED','QUEUED','GENERATING','VALIDATING','SUCCEEDED'"


class OutputRequestRow(Base):
    """R-PRJ runtime aggregate; does not itself imply generation is installed."""

    __tablename__ = "out_requests"
    __table_args__ = (
        UniqueConstraint(
            "output_request_id", "project_id",
            name="uq_out_requests__id_project",
        ),
        UniqueConstraint(
            "project_id", "requested_by", "idempotency_key",
            name="uq_out_requests__idempotency",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_out_requests__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["requested_by"], ["plm.auth_users.user_id"],
            name="fk_out_requests__requester", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["template_version_id"],
            ["plm.prt_template_versions.prototype_template_version_id"],
            name="fk_out_requests__template_version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["job_ref"], ["plm.job_jobs.job_id"],
            name="fk_out_requests__job", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["context_snapshot_ref", "output_request_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.output_request_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_out_requests__context_snapshot", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        CheckConstraint(
            "output_request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND requested_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND context_snapshot_ref <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (job_ref IS NULL OR job_ref <> '00000000-0000-0000-0000-000000000000'::uuid) "
            "AND (current_execution_ref IS NULL OR current_execution_ref <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_out_requests__ids",
        ),
        CheckConstraint(
            "request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING',"
            "'SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')",
            name="ck_out_requests__state",
        ),
        CheckConstraint(
            "output_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND "
            "char_length(policy_version) BETWEEN 1 AND 128 AND "
            "policy_version=btrim(policy_version) AND "
            "char_length(plugin_operation) BETWEEN 1 AND 128 AND "
            "plugin_operation=btrim(plugin_operation) AND "
            "char_length(idempotency_key) BETWEEN 1 AND 255 AND "
            "idempotency_key=btrim(idempotency_key) AND "
            "char_length(trace_id) BETWEEN 1 AND 128 AND trace_id=btrim(trace_id) "
            "AND octet_length(input_fingerprint)=32",
            name="ck_out_requests__request_shape",
        ),
        CheckConstraint(
            "generation_no > 0 AND attempt_count >= 0 AND lock_version >= 0",
            name="ck_out_requests__counters",
        ),
        CheckConstraint(
            "(request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING') "
            "AND completed_at IS NULL AND error_code IS NULL) OR "
            "(request_state='SUCCEEDED' AND completed_at IS NOT NULL AND error_code IS NULL) OR "
            "(request_state='FAILED' AND completed_at IS NOT NULL AND error_code IS NOT NULL) OR "
            "(request_state IN ('CANCEL_REQUESTED','CANCELLED') AND "
            "(completed_at IS NULL OR completed_at>=requested_at))",
            name="ck_out_requests__completion",
        ),
        CheckConstraint(
            "(error_code IS NULL OR error_code ~ '^OUTPUT_[A-Z0-9_]{1,57}$') "
            "AND (started_at IS NULL OR (isfinite(started_at) AND started_at>=requested_at)) "
            "AND (completed_at IS NULL OR (isfinite(completed_at) AND "
            "completed_at>=requested_at AND (started_at IS NULL OR completed_at>=started_at))) "
            "AND isfinite(requested_at) AND isfinite(retention_due_at)",
            name="ck_out_requests__time_error",
        ),
        Index(
            "uq_out_requests__generation_live",
            "project_id", "output_type", "input_fingerprint",
            "template_version_id", "policy_version", "generation_no",
            unique=True,
            postgresql_where=text(
                "request_state IN (" + _LIVE_STATES + ")"
            ),
        ),
        Index(
            "ix_out_requests__project_state_requested",
            "project_id", "request_state", text("requested_at DESC"),
            text("output_request_id DESC"),
        ),
        {"schema": "plm"},
    )

    output_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_type: Mapped[str] = mapped_column(Text, nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    plugin_operation: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    context_snapshot_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    generation_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    request_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'REQUESTED'")
    )
    job_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    current_execution_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    error_code: Mapped[str | None] = mapped_column(Text)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_due_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class OutputContextSnapshotRow(Base):
    """Immutable, minimal and versioned input snapshot for one OutputRequest."""

    __tablename__ = "out_context_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "context_snapshot_id", "output_request_id", "project_id",
            name="uq_out_context_snapshots__identity",
        ),
        UniqueConstraint("output_request_id", name="uq_out_context_snapshots__request"),
        ForeignKeyConstraint(
            ["output_request_id", "project_id"],
            ["plm.out_requests.output_request_id", "plm.out_requests.project_id"],
            name="fk_out_context_snapshots__request", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint(
            "context_snapshot_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND output_request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND context_schema_version=1 AND octet_length(context_fingerprint)=32 "
            "AND jsonb_typeof(context_payload)='object' "
            "AND pg_column_size(context_payload)<=262144 AND isfinite(created_at)",
            name="ck_out_context_snapshots__shape",
        ),
        {"schema": "plm"},
    )

    context_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    output_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    context_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    context_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    context_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class OutputContextSourceRefRow(Base):
    """Fixed, ordered source-version identity refs. Target ownership is Owner-validated."""

    __tablename__ = "out_context_source_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["context_snapshot_id", "output_request_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.output_request_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_out_context_source_refs__snapshot", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "context_snapshot_id", "ref_ordinal",
            name="uq_out_context_source_refs__ordinal",
        ),
        UniqueConstraint(
            "context_snapshot_id", "owner_module", "object_type", "object_id", "version_id",
            name="uq_out_context_source_refs__identity",
        ),
        CheckConstraint(
            "source_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND object_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ref_ordinal BETWEEN 1 AND 10000",
            name="ck_out_context_source_refs__ids",
        ),
        CheckConstraint(
            "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
            "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND "
            "scope IN ('PROJECT','GLOBAL') AND "
            "((scope='PROJECT' AND source_project_id=project_id) OR "
            "(scope='GLOBAL' AND source_project_id IS NULL)) AND "
            "isfinite(added_at)",
            name="ck_out_context_source_refs__scope",
        ),
        Index(
            "ix_out_context_source_refs__fixed_version",
            "owner_module", "object_type", "object_id", "version_id",
        ),
        {"schema": "plm"},
    )

    source_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    context_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ref_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class OutputContextEvidenceRefRow(Base):
    """Fixed, ordered Evidence/Trace refs included in a context snapshot."""

    __tablename__ = "out_context_evidence_refs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["context_snapshot_id", "output_request_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.output_request_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_out_context_evidence_refs__snapshot", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "context_snapshot_id", "ref_ordinal",
            name="uq_out_context_evidence_refs__ordinal",
        ),
        UniqueConstraint(
            "context_snapshot_id", "owner_module", "object_type", "object_id", "version_id",
            name="uq_out_context_evidence_refs__identity",
        ),
        CheckConstraint(
            "evidence_ref_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND object_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND version_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND ref_ordinal BETWEEN 1 AND 10000",
            name="ck_out_context_evidence_refs__ids",
        ),
        CheckConstraint(
            "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
            "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND "
            "scope IN ('PROJECT','GLOBAL') AND "
            "((scope='PROJECT' AND source_project_id=project_id) OR "
            "(scope='GLOBAL' AND source_project_id IS NULL)) AND "
            "octet_length(content_fingerprint)=32 AND isfinite(added_at)",
            name="ck_out_context_evidence_refs__shape",
        ),
        Index(
            "ix_out_context_evidence_refs__fixed_version",
            "owner_module", "object_type", "object_id", "version_id",
        ),
        {"schema": "plm"},
    )

    evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    context_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ref_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
