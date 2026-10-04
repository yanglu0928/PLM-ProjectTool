"""HND-01/HND-02 project analysis identity and immutable version schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer,
    LargeBinary, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_SOURCE_REF = r"source_set_ref ~ '^sha256:[0-9a-f]{64}$'"


class HandoverAnalysisRow(Base):
    __tablename__ = "hnd_analyses"
    __table_args__ = (
        UniqueConstraint("handover_analysis_id", "project_id",
                         name="uq_hnd_analyses__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_hnd_analyses__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_hnd_analyses__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_hnd_analyses__updater", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_versions.handover_analysis_version_id",
             "plm.hnd_analysis_versions.handover_analysis_id",
             "plm.hnd_analysis_versions.project_id"],
            name="fk_hnd_analyses__approved_version", ondelete="NO ACTION",
            use_alter=True,
        ),
        CheckConstraint(
            "char_length(analysis_purpose) BETWEEN 1 AND 255 "
            "AND analysis_purpose=btrim(analysis_purpose)",
            name="ck_hnd_analyses__purpose",
        ),
        CheckConstraint(_SOURCE_REF, name="ck_hnd_analyses__source_ref"),
        CheckConstraint("analysis_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                        name="ck_hnd_analyses__state"),
        CheckConstraint("lock_version>=0", name="ck_hnd_analyses__lock"),
        Index("ix_hnd_analyses__project_state", "project_id", "analysis_state",
              "handover_analysis_id"),
        {"schema": "plm"},
    )

    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analysis_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    source_set_ref: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'"),
    )
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"),
    )


class HandoverAnalysisVersionRow(Base):
    __tablename__ = "hnd_analysis_versions"
    __table_args__ = (
        UniqueConstraint("handover_analysis_version_id", "handover_analysis_id",
                         "project_id", name="uq_hnd_versions__id_analysis_project"),
        UniqueConstraint("handover_analysis_id", "version_no",
                         name="uq_hnd_versions__analysis_no"),
        ForeignKeyConstraint(
            ["handover_analysis_id", "project_id"],
            ["plm.hnd_analyses.handover_analysis_id", "plm.hnd_analyses.project_id"],
            name="fk_hnd_versions__analysis", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_ref", "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_versions.handover_analysis_version_id",
             "plm.hnd_analysis_versions.handover_analysis_id",
             "plm.hnd_analysis_versions.project_id"],
            name="fk_hnd_versions__supersedes", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["capability_baseline_version_ref", "capability_baseline_id"],
            ["plm.cap_baseline_versions.baseline_version_id",
             "plm.cap_baseline_versions.baseline_id"],
            name="fk_hnd_versions__capability_version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_hnd_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"],
                             ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_hnd_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_hnd_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_hnd_versions__number"),
        CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_hnd_versions__state",
        ),
        CheckConstraint(_SOURCE_REF, name="ck_hnd_versions__source_ref"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_hnd_versions__fingerprint"),
        CheckConstraint(
            "declared_source_count>0 AND declared_item_count>0 "
            "AND declared_evidence_count>=0 AND declared_capability_ref_count>=0 "
            "AND declared_ai_task_count>=0", name="ck_hnd_versions__counts",
        ),
        CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_hnd_versions__review_shape",
        ),
        Index("ix_hnd_versions__analysis_created", "handover_analysis_id", "created_at"),
        Index("uq_hnd_versions__analysis_in_review", "handover_analysis_id",
              unique=True, postgresql_where=text("version_state='IN_REVIEW'")),
        Index("uq_hnd_versions__analysis_approved", "handover_analysis_id",
              unique=True, postgresql_where=text("version_state='APPROVED'")),
        {"schema": "plm"},
    )

    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    source_set_ref: Mapped[str] = mapped_column(Text, nullable=False)
    capability_baseline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability_baseline_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    declared_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_capability_ref_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_ai_task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class HandoverSourceDocumentRefRow(Base):
    __tablename__ = "hnd_analysis_source_document_refs"
    __table_args__ = (
        UniqueConstraint("handover_analysis_version_id", "document_version_id",
                         name="uq_hnd_source_docs__version_document"),
        UniqueConstraint("handover_analysis_version_id", "ordinal",
                         name="uq_hnd_source_docs__version_ordinal"),
        ForeignKeyConstraint(
            ["handover_analysis_version_id", "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_versions.handover_analysis_version_id",
             "plm.hnd_analysis_versions.handover_analysis_id",
             "plm.hnd_analysis_versions.project_id"],
            name="fk_hnd_source_docs__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_hnd_source_docs__document_version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_hnd_source_docs__ordinal"),
        Index("ix_hnd_source_docs__document_version", "document_version_id"),
        {"schema": "plm"},
    )

    source_document_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class HandoverAITaskRefRow(Base):
    __tablename__ = "hnd_analysis_ai_task_refs"
    __table_args__ = (
        UniqueConstraint("handover_analysis_version_id", "ai_task_id",
                         name="uq_hnd_ai_refs__version_task"),
        UniqueConstraint("handover_analysis_version_id", "ordinal",
                         name="uq_hnd_ai_refs__version_ordinal"),
        ForeignKeyConstraint(
            ["handover_analysis_version_id", "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_versions.handover_analysis_version_id",
             "plm.hnd_analysis_versions.handover_analysis_id",
             "plm.hnd_analysis_versions.project_id"],
            name="fk_hnd_ai_refs__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["ai_task_id", "task_scope", "project_id"],
            ["plm.ai_tasks.ai_task_id", "plm.ai_tasks.scope", "plm.ai_tasks.project_id"],
            name="fk_hnd_ai_refs__task", ondelete="NO ACTION",
        ),
        CheckConstraint("task_scope='PROJECT'", name="ck_hnd_ai_refs__scope"),
        CheckConstraint("ordinal>=0", name="ck_hnd_ai_refs__ordinal"),
        {"schema": "plm"},
    )

    ai_task_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ai_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PROJECT'"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class HandoverAnalysisItemRow(Base):
    __tablename__ = "hnd_analysis_items"
    __table_args__ = (
        UniqueConstraint("analysis_item_row_id", "handover_analysis_version_id",
                         "handover_analysis_id", "project_id",
                         name="uq_hnd_items__row_version_analysis_project"),
        UniqueConstraint("handover_analysis_version_id", "analysis_item_id",
                         name="uq_hnd_items__version_stable"),
        UniqueConstraint("handover_analysis_version_id", "ordinal",
                         name="uq_hnd_items__version_ordinal"),
        ForeignKeyConstraint(
            ["handover_analysis_version_id", "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_versions.handover_analysis_version_id",
             "plm.hnd_analysis_versions.handover_analysis_id",
             "plm.hnd_analysis_versions.project_id"],
            name="fk_hnd_items__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_hnd_items__ordinal"),
        CheckConstraint("item_type IN ('GAP','MISSING','CONFLICT','RISK','SCOPE','NEED_CONFIRM')",
                        name="ck_hnd_items__type"),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL') AND "
                        "priority IN ('LOW','MEDIUM','HIGH','URGENT')",
                        name="ck_hnd_items__classification"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title) AND "
                        "char_length(statement) BETWEEN 1 AND 4000 AND statement=btrim(statement) AND "
                        "char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
                        name="ck_hnd_items__texts"),
        CheckConstraint("recommendation IS NULL OR (char_length(recommendation) BETWEEN 1 AND 2000 "
                        "AND recommendation=btrim(recommendation))",
                        name="ck_hnd_items__recommendation"),
        CheckConstraint("item_state IN ('CANDIDATE','CONFIRMED','RESOLVED','ACCEPTED_RISK',"
                        "'REJECTED','SUPERSEDED')", name="ck_hnd_items__state"),
        CheckConstraint("jsonb_typeof(required_input_spec)='object'",
                        name="ck_hnd_items__input_spec"),
        Index("ix_hnd_items__version_ordinal", "handover_analysis_version_id", "ordinal"),
        {"schema": "plm"},
    )

    analysis_item_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    analysis_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)
    confirmation_question: Mapped[str | None] = mapped_column(Text)
    required_input_spec: Mapped[dict] = mapped_column(JSONB, nullable=False,
                                                      server_default=text("'{}'::jsonb"))
    source_missing: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                  server_default=text("false"))
    item_state: Mapped[str] = mapped_column(Text, nullable=False,
                                             server_default=text("'CANDIDATE'"))


class HandoverItemEvidenceRefRow(Base):
    __tablename__ = "hnd_item_evidence_refs"
    __table_args__ = (
        UniqueConstraint("analysis_item_row_id", "evidence_id",
                         name="uq_hnd_item_evidence__item_evidence"),
        UniqueConstraint("analysis_item_row_id", "ordinal",
                         name="uq_hnd_item_evidence__item_ordinal"),
        ForeignKeyConstraint(
            ["analysis_item_row_id", "handover_analysis_version_id",
             "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_items.analysis_item_row_id",
             "plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.handover_analysis_id",
             "plm.hnd_analysis_items.project_id"],
            name="fk_hnd_item_evidence__item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_hnd_item_evidence__evidence", ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_hnd_item_evidence__ordinal"),
        Index("ix_hnd_item_evidence__evidence", "evidence_id"),
        {"schema": "plm"},
    )

    item_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    analysis_item_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class HandoverItemCapabilityRefRow(Base):
    __tablename__ = "hnd_item_capability_refs"
    __table_args__ = (
        UniqueConstraint("analysis_item_row_id", "baseline_version_id", "capability_item_id",
                         name="uq_hnd_item_capability__item_capability"),
        UniqueConstraint("analysis_item_row_id", "ordinal",
                         name="uq_hnd_item_capability__item_ordinal"),
        ForeignKeyConstraint(
            ["analysis_item_row_id", "handover_analysis_version_id",
             "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_items.analysis_item_row_id",
             "plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.handover_analysis_id",
             "plm.hnd_analysis_items.project_id"],
            name="fk_hnd_item_capability__item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["baseline_version_id", "capability_item_id"],
            ["plm.cap_items.baseline_version_id", "plm.cap_items.capability_item_id"],
            name="fk_hnd_item_capability__capability", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_hnd_item_capability__ordinal"),
        {"schema": "plm"},
    )

    item_capability_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    analysis_item_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class HandoverItemOptionRow(Base):
    __tablename__ = "hnd_item_options"
    __table_args__ = (
        UniqueConstraint("analysis_item_row_id", "option_code",
                         name="uq_hnd_item_options__item_code"),
        UniqueConstraint("analysis_item_row_id", "ordinal",
                         name="uq_hnd_item_options__item_ordinal"),
        ForeignKeyConstraint(
            ["analysis_item_row_id", "handover_analysis_version_id",
             "handover_analysis_id", "project_id"],
            ["plm.hnd_analysis_items.analysis_item_row_id",
             "plm.hnd_analysis_items.handover_analysis_version_id",
             "plm.hnd_analysis_items.handover_analysis_id",
             "plm.hnd_analysis_items.project_id"],
            name="fk_hnd_item_options__item", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_hnd_item_options__ordinal"),
        CheckConstraint("option_code ~ '^[A-Z][A-Z0-9_-]{0,31}$'",
                        name="ck_hnd_item_options__code"),
        CheckConstraint("char_length(label) BETWEEN 1 AND 255 AND label=btrim(label)",
                        name="ck_hnd_item_options__label"),
        {"schema": "plm"},
    )

    item_option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    analysis_item_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    option_code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
