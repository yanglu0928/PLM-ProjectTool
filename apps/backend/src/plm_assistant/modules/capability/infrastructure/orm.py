"""CAP-01/CAP-02 GLOBAL baseline, immutable version, item and source schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_SOURCE_REF = r"source_collection_ref ~ '^sha256:[0-9a-f]{64}$'"


class CapabilityBaselineRow(Base):
    __tablename__ = "cap_baselines"
    __table_args__ = (
        UniqueConstraint("baseline_code", name="uq_cap_baselines__code"),
        UniqueConstraint("baseline_id", "source_collection_ref",
                         name="uq_cap_baselines__id_source"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "baseline_id"],
            ["plm.cap_baseline_versions.baseline_version_id",
             "plm.cap_baseline_versions.baseline_id"],
            name="fk_cap_baselines__approved_version", ondelete="NO ACTION",
            use_alter=True,
        ),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_cap_baselines__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_cap_baselines__updater", ondelete="NO ACTION"),
        CheckConstraint(
            "baseline_code ~ '^[A-Z][A-Z0-9_.-]{0,63}$'",
            name="ck_cap_baselines__code",
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                        name="ck_cap_baselines__name"),
        CheckConstraint(
            "description IS NULL OR (char_length(description) BETWEEN 1 AND 2000 "
            "AND description=btrim(description))",
            name="ck_cap_baselines__description",
        ),
        CheckConstraint("baseline_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                        name="ck_cap_baselines__state"),
        CheckConstraint(_SOURCE_REF, name="ck_cap_baselines__source_ref"),
        CheckConstraint("lock_version>=0", name="ck_cap_baselines__lock"),
        Index("ix_cap_baselines__state_code", "baseline_state", "baseline_code"),
        {"schema": "plm"},
    )

    baseline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    baseline_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    baseline_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'")
    )
    source_collection_ref: Mapped[str] = mapped_column(Text, nullable=False)
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
        BigInteger, nullable=False, server_default=text("0")
    )


class CapabilityBaselineVersionRow(Base):
    __tablename__ = "cap_baseline_versions"
    __table_args__ = (
        UniqueConstraint("baseline_version_id", "baseline_id",
                         name="uq_cap_versions__id_baseline"),
        UniqueConstraint("baseline_id", "version_no",
                         name="uq_cap_versions__baseline_no"),
        ForeignKeyConstraint(["baseline_id"], ["plm.cap_baselines.baseline_id"],
                             name="fk_cap_versions__baseline", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["supersedes_version_ref", "baseline_id"],
            ["plm.cap_baseline_versions.baseline_version_id",
             "plm.cap_baseline_versions.baseline_id"],
            name="fk_cap_versions__supersedes", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_cap_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"],
                             ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_cap_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_cap_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_cap_versions__number"),
        CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')",
            name="ck_cap_versions__state",
        ),
        CheckConstraint(_SOURCE_REF, name="ck_cap_versions__source_ref"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_cap_versions__fingerprint"),
        CheckConstraint(
            "declared_item_count>0 AND declared_document_ref_count>0 "
            "AND declared_evidence_ref_count>=declared_item_count",
            name="ck_cap_versions__counts",
        ),
        CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_cap_versions__review_shape",
        ),
        Index("ix_cap_versions__baseline_created", "baseline_id", "created_at"),
        Index(
            "uq_cap_versions__baseline_in_review", "baseline_id", unique=True,
            postgresql_where=text("version_state='IN_REVIEW'"),
        ),
        {"schema": "plm"},
    )

    baseline_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    baseline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'DRAFT'")
    )
    source_collection_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    declared_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_document_ref_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_evidence_ref_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class CapabilityItemRow(Base):
    __tablename__ = "cap_items"
    __table_args__ = (
        UniqueConstraint("capability_item_row_id", "baseline_version_id", "baseline_id",
                         name="uq_cap_items__row_version_baseline"),
        UniqueConstraint("baseline_version_id", "capability_item_id",
                         name="uq_cap_items__version_stable"),
        UniqueConstraint("baseline_version_id", "capability_code",
                         name="uq_cap_items__version_code"),
        UniqueConstraint("baseline_version_id", "ordinal",
                         name="uq_cap_items__version_ordinal"),
        ForeignKeyConstraint(
            ["baseline_version_id", "baseline_id"],
            ["plm.cap_baseline_versions.baseline_version_id",
             "plm.cap_baseline_versions.baseline_id"],
            name="fk_cap_items__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_cap_items__ordinal"),
        CheckConstraint("capability_code ~ '^[A-Z][A-Z0-9_.-]{0,63}$'",
                        name="ck_cap_items__code"),
        CheckConstraint(
            "char_length(domain_name) BETWEEN 1 AND 255 AND domain_name=btrim(domain_name) "
            "AND char_length(module_name) BETWEEN 1 AND 255 AND module_name=btrim(module_name) "
            "AND char_length(feature_name) BETWEEN 1 AND 255 AND feature_name=btrim(feature_name)",
            name="ck_cap_items__classification",
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                        name="ck_cap_items__name"),
        CheckConstraint(
            "char_length(description) BETWEEN 1 AND 2000 AND description=btrim(description) "
            "AND char_length(boundary_text) BETWEEN 1 AND 2000 AND boundary_text=btrim(boundary_text)",
            name="ck_cap_items__texts",
        ),
        CheckConstraint(
            "cardinality(prerequisites)<=100 AND cardinality(interface_refs)<=100 "
            "AND array_position(prerequisites,NULL) IS NULL "
            "AND array_position(interface_refs,NULL) IS NULL",
            name="ck_cap_items__arrays",
        ),
        CheckConstraint("item_state IN ('AVAILABLE','DEPRECATED','WITHDRAWN')",
                        name="ck_cap_items__state"),
        Index("ix_cap_items__version_ordinal", "baseline_version_id", "ordinal"),
        {"schema": "plm"},
    )

    capability_item_row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    domain_name: Mapped[str] = mapped_column(Text, nullable=False)
    module_name: Mapped[str] = mapped_column(Text, nullable=False)
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_text: Mapped[str] = mapped_column(Text, nullable=False)
    prerequisites: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    interface_refs: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    item_state: Mapped[str] = mapped_column(Text, nullable=False)


class CapabilityItemDocumentRefRow(Base):
    __tablename__ = "cap_item_document_refs"
    __table_args__ = (
        UniqueConstraint("capability_item_row_id", "document_version_id",
                         name="uq_cap_item_docs__item_version"),
        UniqueConstraint("capability_item_row_id", "ordinal",
                         name="uq_cap_item_docs__item_ordinal"),
        ForeignKeyConstraint(
            ["capability_item_row_id", "baseline_version_id", "baseline_id"],
            ["plm.cap_items.capability_item_row_id",
             "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"],
            name="fk_cap_item_docs__item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "document_id"],
            ["plm.doc_document_versions.document_version_id",
             "plm.doc_document_versions.document_id"],
            name="fk_cap_item_docs__document_version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_cap_item_docs__ordinal"),
        Index("ix_cap_item_docs__document_version", "document_version_id"),
        {"schema": "plm"},
    )

    capability_item_document_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    capability_item_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class CapabilityItemEvidenceRefRow(Base):
    __tablename__ = "cap_item_evidence_refs"
    __table_args__ = (
        UniqueConstraint("capability_item_row_id", "evidence_id",
                         name="uq_cap_item_evidence__item_evidence"),
        UniqueConstraint("capability_item_row_id", "ordinal",
                         name="uq_cap_item_evidence__item_ordinal"),
        ForeignKeyConstraint(
            ["capability_item_row_id", "baseline_version_id", "baseline_id"],
            ["plm.cap_items.capability_item_row_id",
             "plm.cap_items.baseline_version_id", "plm.cap_items.baseline_id"],
            name="fk_cap_item_evidence__item", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_cap_item_evidence__evidence", ondelete="NO ACTION"),
        CheckConstraint("ordinal>=0", name="ck_cap_item_evidence__ordinal"),
        Index("ix_cap_item_evidence__evidence", "evidence_id"),
        {"schema": "plm"},
    )

    capability_item_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    capability_item_row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    baseline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
