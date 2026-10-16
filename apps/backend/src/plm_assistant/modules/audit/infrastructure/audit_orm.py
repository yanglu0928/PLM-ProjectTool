"""AUD-01 append-only AuditEvent ORM; no request/response body columns."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, LargeBinary, Text, desc, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


TARGET_PAIR_CHECK = """
(
    target_owner_module IS NULL AND target_object_type IS NULL
    AND target_object_id IS NULL AND target_version_id IS NULL
) OR (
    target_owner_module IS NOT NULL AND target_object_type IS NOT NULL
    AND target_object_id IS NOT NULL AND (
        (target_owner_module = 'platform' AND target_object_type IN ('PLT-01','PLT-02')) OR
        (target_owner_module = 'auth' AND target_object_type IN ('AUT-01','AUT-02')) OR
        (target_owner_module = 'project' AND target_object_type IN ('PRJ-01','PRJ-02','PRJ-03')) OR
        (target_owner_module = 'workflow' AND target_object_type IN ('WFL-01','WFL-02')) OR
        (target_owner_module = 'review' AND target_object_type IN ('RVW-01','RVW-02')) OR
        (target_owner_module = 'trace' AND target_object_type = 'TRC-01') OR
        (target_owner_module = 'audit' AND target_object_type = 'AUD-01') OR
        (target_owner_module = 'license' AND target_object_type IN ('LIC-01','LIC-02','LIC-03')) OR
        (target_owner_module = 'document' AND target_object_type IN ('DOC-01','DOC-02','DOC-03','DOC-04')) OR
        (target_owner_module = 'evidence' AND target_object_type IN ('EVD-01','EVD-02')) OR
        (target_owner_module = 'jobs' AND target_object_type IN ('JOB-01','JOB-02')) OR
        (target_owner_module = 'ai' AND target_object_type IN ('AI-01','AI-02','AI-03','AI-04')) OR
        (target_owner_module = 'rag' AND target_object_type IN ('RAG-01','RAG-02','RAG-03','RAG-04')) OR
        (target_owner_module = 'capability' AND target_object_type IN ('CAP-01','CAP-02')) OR
        (target_owner_module = 'handover' AND target_object_type IN ('HND-01','HND-02','HND-03')) OR
        (target_owner_module = 'survey' AND target_object_type IN ('SRV-01','SRV-02','SRV-03','SRV-04','SRV-05')) OR
        (target_owner_module = 'requirement' AND target_object_type IN ('REQ-01','REQ-02','REQ-03','REQ-04')) OR
        (target_owner_module = 'prototype' AND target_object_type IN ('PRT-01','PRT-02','PRT-03','PRT-04','PRT-05')) OR
        (target_owner_module = 'solution' AND target_object_type IN ('SOL-01','SOL-02','SOL-03','SOL-04','SOL-05','SOL-06')) OR
        (target_owner_module = 'plan' AND target_object_type IN ('PLN-01','PLN-02','PLN-03')) OR
        (target_owner_module = 'output' AND target_object_type IN ('OUT-01','OUT-02')) OR
        (target_owner_module = 'plugin' AND target_object_type IN ('PLG-01','PLG-02','PLG-03'))
    )
)
"""


class AuditEventRow(Base):
    __tablename__ = "aud_events"
    __table_args__ = (
        CheckConstraint("event_scope IN ('DEPLOYMENT', 'PROJECT')", name="ck_aud_events__event_scope"),
        CheckConstraint("(event_scope = 'DEPLOYMENT' AND target_project_id IS NULL) OR (event_scope = 'PROJECT' AND target_project_id IS NOT NULL)", name="ck_aud_events__project_scope"),
        CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'UNRESOLVED')", name="ck_aud_events__actor_type"),
        CheckConstraint("(actor_type = 'USER' AND actor_id IS NOT NULL AND original_actor_id IS NULL AND actor_hint_digest IS NULL) OR (actor_type = 'SYSTEM' AND actor_id IS NOT NULL AND original_actor_id IS NOT NULL AND actor_hint_digest IS NULL) OR (actor_type = 'UNRESOLVED' AND actor_id IS NULL AND original_actor_id IS NULL)", name="ck_aud_events__actor_shape"),
        CheckConstraint("actor_hint_digest IS NULL OR octet_length(actor_hint_digest) = 32", name="ck_aud_events__actor_hint_digest"),
        CheckConstraint("action ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__action"),
        CheckConstraint("outcome IN ('SUCCESS', 'DENIED', 'FAILED')", name="ck_aud_events__outcome"),
        CheckConstraint(TARGET_PAIR_CHECK, name="ck_aud_events__target_pair"),
        CheckConstraint("reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__reason_code"),
        CheckConstraint("before_state IS NULL OR before_state ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__before_state"),
        CheckConstraint("after_state IS NULL OR after_state ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_aud_events__after_state"),
        Index("ix_aud_events__project_time", "target_project_id", desc("occurred_at"), desc("audit_event_id")),
        Index("ix_aud_events__target_time", "target_owner_module", "target_object_type", "target_object_id", "target_version_id", desc("occurred_at")),
        Index("ix_aud_events__actor_time", "actor_id", desc("occurred_at"), desc("audit_event_id")),
    )

    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_scope: Mapped[str] = mapped_column(Text, nullable=False)
    target_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    original_actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_hint_digest: Mapped[bytes | None] = mapped_column(LargeBinary)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    target_owner_module: Mapped[str | None] = mapped_column(Text)
    target_object_type: Mapped[str | None] = mapped_column(Text)
    target_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason_code: Mapped[str | None] = mapped_column(Text)
    before_state: Mapped[str | None] = mapped_column(Text)
    after_state: Mapped[str | None] = mapped_column(Text)
