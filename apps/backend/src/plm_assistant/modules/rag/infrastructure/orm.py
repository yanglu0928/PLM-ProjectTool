"""RAG-01 DocumentChunk source and full-text projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class DocumentChunkRow(Base):
    """A source-bound chunk generation; it is not an Embedding or Index record."""

    __tablename__ = "rag_document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_chunks__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["document_version_ref"],
            ["plm.doc_document_versions.document_version_id"],
            name="fk_rag_chunks__document_version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["parse_record_ref"], ["plm.doc_parse_records.parse_record_id"],
            name="fk_rag_chunks__parse_record", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["parse_result_ref"],
            ["plm.doc_parse_result_refs.parse_result_ref_id"],
            name="fk_rag_chunks__parse_result", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_rag_chunks__creator", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "document_version_ref", "parse_record_ref", "chunk_profile",
            "chunk_profile_version", "chunk_ordinal",
            name="uq_rag_chunks__source_generation_ordinal",
        ),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_chunks__scope_project",
        ),
        CheckConstraint(
            "chunk_profile ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND chunk_profile_version BETWEEN 1 AND 2147483647 "
            "AND chunk_ordinal BETWEEN 0 AND 2147483647",
            name="ck_rag_chunks__generation",
        ),
        CheckConstraint(
            "jsonb_typeof(source_locator)='object' "
            "AND source_locator ? 'locator_type'",
            name="ck_rag_chunks__locator",
        ),
        CheckConstraint(
            "source_type IN ('CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY',"
            "'REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER')",
            name="ck_rag_chunks__source_type",
        ),
        CheckConstraint(
            "char_length(search_body) BETWEEN 1 AND 65535 "
            "AND octet_length(text_fingerprint)=32",
            name="ck_rag_chunks__text",
        ),
        CheckConstraint(
            "jsonb_typeof(metadata_snapshot)='object'",
            name="ck_rag_chunks__metadata",
        ),
        CheckConstraint(
            "chunk_state IN ('ACTIVE','RESTRICTED','REVOKED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND isfinite(created_at)",
            name="ck_rag_chunks__state",
        ),
        Index("ix_rag_chunks__search_gin", "search_vector", postgresql_using="gin"),
        Index(
            "ix_rag_chunks__project_source_state", "project_id",
            "document_version_ref", "chunk_state", "chunk_id",
        ),
        Index(
            "ix_rag_chunks__global_source_state", "document_version_ref",
            "chunk_state", "chunk_id",
            postgresql_where=text("scope='GLOBAL'"),
        ),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parse_record_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parse_result_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_profile: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    search_body: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple'::regconfig, search_body)", persisted=True),
    )
    text_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    metadata_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb"),
    )
    chunk_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"),
    )


class EmbeddingIndexRow(Base):
    """A planned, model-bound index generation with an exact source snapshot."""

    __tablename__ = "rag_embedding_indexes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_indexes__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_model_ref"], ["plm.ai_models.ai_model_id"],
            name="fk_rag_indexes__model", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_rag_indexes__creator", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "scope", "project_id", "index_purpose", "index_version",
            name="uq_rag_indexes__purpose_version",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_indexes__scope_project",
        ),
        CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND chunk_profile ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_rag_indexes__refs",
        ),
        CheckConstraint(
            "embedding_dimension BETWEEN 1 AND 2000 "
            "AND chunk_profile_version BETWEEN 1 AND 2147483647 "
            "AND index_version BETWEEN 1 AND 9223372036854775807",
            name="ck_rag_indexes__versions",
        ),
        CheckConstraint(
            "source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND octet_length(source_snapshot_fingerprint)=32",
            name="ck_rag_indexes__snapshot",
        ),
        CheckConstraint(
            "index_state IN ('PLANNED','BUILDING','READY','ACTIVE','FAILED','RETIRED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_indexes__state",
        ),
        Index(
            "uq_rag_indexes__active_purpose", "scope", "project_id",
            "index_purpose", unique=True,
            postgresql_where=text("index_state='ACTIVE'"),
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_rag_indexes__project_purpose_version", "project_id",
            "index_purpose", text("index_version DESC"), "embedding_index_id",
        ),
    )

    embedding_index_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    index_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_profile: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_chunk_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_snapshot_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    index_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    index_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'PLANNED'"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"),
    )


class IndexSourceChunkRow(Base):
    """An immutable exact member of an EmbeddingIndex source snapshot."""

    __tablename__ = "rag_index_source_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["embedding_index_id"],
            ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_sources__index", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
            name="fk_rag_index_sources__chunk", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_sources__project", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "embedding_index_id", "source_ordinal",
            name="uq_rag_index_sources__ordinal",
        ),
        UniqueConstraint(
            "embedding_index_id", "chunk_id",
            name="uq_rag_index_sources__chunk",
        ),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_sources__scope_project",
        ),
        CheckConstraint(
            "source_ordinal BETWEEN 1 AND 1000000000 "
            "AND octet_length(chunk_text_fingerprint)=32 "
            "AND created_xid>0",
            name="ck_rag_index_sources__shape",
        ),
        Index(
            "ix_rag_index_sources__chunk", "chunk_id", "embedding_index_id",
        ),
    )

    index_source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    chunk_text_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )
