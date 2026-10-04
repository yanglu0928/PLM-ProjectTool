"""RAG-01 DocumentChunk source and full-text projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from pgvector.sqlalchemy import Vector

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
        UniqueConstraint(
            "embedding_index_id", "embedding_model_ref", "embedding_dimension",
            name="uq_rag_indexes__id_model_dimension",
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
        UniqueConstraint(
            "embedding_index_id", "chunk_id", "chunk_text_fingerprint",
            name="uq_rag_index_sources__chunk_fingerprint",
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


class EmbeddingRecordRow(Base):
    """An immutable successful vector bound to one exact Index source Chunk."""

    __tablename__ = "rag_embedding_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_embeddings__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_embeddings__index_model_dimension", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_index_id", "chunk_id", "chunk_text_fingerprint"],
            ["plm.rag_index_source_chunks.embedding_index_id",
             "plm.rag_index_source_chunks.chunk_id",
             "plm.rag_index_source_chunks.chunk_text_fingerprint"],
            name="fk_rag_embeddings__source_chunk", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["egress_authorization_ref"],
            ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_rag_embeddings__egress_authorization", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_embeddings__scope_project",
        ),
        CheckConstraint(
            "embedding_dimension IN (768,1024) "
            "AND vector_dims(embedding_vector)=embedding_dimension",
            name="ck_rag_embeddings__dimension",
        ),
        CheckConstraint(
            "octet_length(chunk_text_fingerprint)=32 "
            "AND octet_length(vector_fingerprint)=32",
            name="ck_rag_embeddings__fingerprints",
        ),
        CheckConstraint(
            "embedding_state IN ('AVAILABLE','FAILED','REVOKED') "
            "AND (provider_request_ref IS NULL OR "
            "(char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]')) "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_embeddings__state",
        ),
        Index(
            "uq_rag_embeddings__index_chunk_available",
            "embedding_index_id", "chunk_id", unique=True,
            postgresql_where=text("embedding_state='AVAILABLE'"),
        ),
        Index(
            "ix_rag_embeddings__project_index", "project_id",
            "embedding_index_id", "embedding_record_id",
        ),
        Index(
            "ix_rag_embeddings__v768_hnsw",
            text("(embedding_vector::vector(768)) vector_cosine_ops"),
            postgresql_using="hnsw",
            postgresql_with={"m": 32, "ef_construction": 200},
            postgresql_where=text(
                "embedding_state='AVAILABLE' AND embedding_dimension=768"
            ),
        ),
        Index(
            "ix_rag_embeddings__v1024_hnsw",
            text("(embedding_vector::vector(1024)) vector_cosine_ops"),
            postgresql_using="hnsw",
            postgresql_with={"m": 32, "ef_construction": 200},
            postgresql_where=text(
                "embedding_state='AVAILABLE' AND embedding_dimension=1024"
            ),
        ),
    )

    embedding_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    vector_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    embedding_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'AVAILABLE'"),
    )
    provider_request_ref: Mapped[str | None] = mapped_column(Text)
    egress_authorization_ref: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class EmbeddingBuildRow(Base):
    """One immutable batch plan and unique Job owner for an Index generation."""

    __tablename__ = "rag_embedding_builds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_builds__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_builds__index_model_dimension", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["build_job_ref"], ["plm.job_jobs.job_id"],
            name="fk_rag_builds__job", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_rag_builds__creator", ondelete="NO ACTION",
        ),
        UniqueConstraint("embedding_index_id", name="uq_rag_builds__index"),
        UniqueConstraint("build_job_ref", name="uq_rag_builds__job"),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_builds__scope_project",
        ),
        CheckConstraint(
            "build_generation BETWEEN 1 AND 9223372036854775807 "
            "AND embedding_dimension IN (768,1024) "
            "AND source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND batch_count BETWEEN 1 AND 100000",
            name="ck_rag_builds__counts",
        ),
        CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 "
            "AND octet_length(authorization_set_fingerprint)=32 "
            "AND octet_length(build_fingerprint)=32",
            name="ck_rag_builds__fingerprints",
        ),
        CheckConstraint(
            "build_state IN ('PLANNED','RUNNING','SUCCEEDED','FAILED','UNKNOWN','CANCELLED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_builds__state",
        ),
        Index(
            "ix_rag_builds__project_state", "project_id", "build_state",
            "embedding_build_id",
        ),
    )

    embedding_build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    build_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    build_job_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_chunk_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_snapshot_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    batch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_set_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    build_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    build_state: Mapped[str] = mapped_column(
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


class EmbeddingBuildBatchRow(Base):
    """An exact, individually authorized external request in a Build plan."""

    __tablename__ = "rag_embedding_build_batches"
    __table_args__ = (
        ForeignKeyConstraint(
            ["embedding_build_id"], ["plm.rag_embedding_builds.embedding_build_id"],
            name="fk_rag_build_batches__build", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["egress_authorization_ref"],
            ["plm.ai_egress_authorizations.authorization_id"],
            name="fk_rag_build_batches__authorization", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "embedding_build_id", "batch_ordinal",
            name="uq_rag_build_batches__ordinal",
        ),
        UniqueConstraint(
            "embedding_build_id", "source_first_ordinal",
            name="uq_rag_build_batches__source_start",
        ),
        UniqueConstraint(
            "egress_authorization_ref", name="uq_rag_build_batches__authorization",
        ),
        CheckConstraint(
            "batch_ordinal BETWEEN 1 AND 100000 "
            "AND source_first_ordinal BETWEEN 1 AND 1000000000 "
            "AND source_record_count BETWEEN 1 AND 1000 "
            "AND payload_bytes BETWEEN 1 AND 100000000 "
            "AND input_tokens BETWEEN 1 AND 1048576",
            name="ck_rag_build_batches__bounds",
        ),
        CheckConstraint(
            "octet_length(source_batch_fingerprint)=32 "
            "AND octet_length(payload_fingerprint)=32",
            name="ck_rag_build_batches__fingerprints",
        ),
        CheckConstraint(
            "batch_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','UNKNOWN','CANCELLED') "
            "AND lock_version BETWEEN 0 AND 9223372036854775807 "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_build_batches__state",
        ),
        CheckConstraint(
            "(batch_state='PENDING' AND send_fencing_token IS NULL "
            "AND provider_request_ref IS NULL AND error_code IS NULL "
            "AND started_at IS NULL AND completed_at IS NULL) OR "
            "(batch_state='RUNNING' AND send_fencing_token>0 "
            "AND error_code IS NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(batch_state='SUCCEEDED' AND send_fencing_token>0 "
            "AND error_code IS NULL AND started_at IS NOT NULL "
            "AND completed_at>=started_at) OR "
            "(batch_state IN ('FAILED','UNKNOWN','CANCELLED') "
            "AND error_code IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at>=started_at)",
            name="ck_rag_build_batches__lifecycle",
        ),
        CheckConstraint(
            "(provider_request_ref IS NULL OR "
            "(char_length(provider_request_ref) BETWEEN 1 AND 255 "
            "AND provider_request_ref !~ '[\\r\\n]')) "
            "AND (error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_rag_build_batches__result",
        ),
        Index(
            "ix_rag_build_batches__build_state", "embedding_build_id",
            "batch_state", "batch_ordinal",
        ),
    )

    embedding_build_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_build_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_first_ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_batch_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    egress_authorization_ref: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    batch_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'PENDING'"),
    )
    send_fencing_token: Mapped[int | None] = mapped_column(BigInteger)
    provider_request_ref: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
    )
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


class EmbeddingIndexValidationRow(Base):
    """Immutable technical evidence for one complete EmbeddingIndex build."""

    __tablename__ = "rag_embedding_index_validations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_validations__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_index_id", "embedding_model_ref", "embedding_dimension"],
            ["plm.rag_embedding_indexes.embedding_index_id",
             "plm.rag_embedding_indexes.embedding_model_ref",
             "plm.rag_embedding_indexes.embedding_dimension"],
            name="fk_rag_index_validations__index_model_dimension",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_build_id"], ["plm.rag_embedding_builds.embedding_build_id"],
            name="fk_rag_index_validations__build", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["validated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_validations__validator", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "embedding_index_id", name="uq_rag_index_validations__index",
        ),
        UniqueConstraint(
            "embedding_build_id", name="uq_rag_index_validations__build",
        ),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_validations__scope_project",
        ),
        CheckConstraint(
            "embedding_dimension IN (768,1024) "
            "AND source_chunk_count BETWEEN 1 AND 1000000000 "
            "AND available_record_count BETWEEN 0 AND 1000000000 "
            "AND missing_record_count BETWEEN 0 AND 1000000000 "
            "AND extra_record_count BETWEEN 0 AND 1000000000 "
            "AND duplicate_record_count BETWEEN 0 AND 1000000000 "
            "AND invalid_record_count BETWEEN 0 AND 1000000000 "
            "AND expected_batch_count BETWEEN 1 AND 100000 "
            "AND succeeded_batch_count BETWEEN 0 AND 100000",
            name="ck_rag_index_validations__counts",
        ),
        CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 "
            "AND octet_length(build_fingerprint)=32 "
            "AND octet_length(record_set_fingerprint)=32 "
            "AND octet_length(validation_fingerprint)=32 "
            "AND (hnsw_catalog_fingerprint IS NULL OR "
            "octet_length(hnsw_catalog_fingerprint)=32) "
            "AND (plan_fingerprint IS NULL OR octet_length(plan_fingerprint)=32)",
            name="ck_rag_index_validations__fingerprints",
        ),
        CheckConstraint(
            "validation_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' "
            "AND hnsw_index_name ~ '^ix_rag_embeddings__v(768|1024)_hnsw$' "
            "AND exact_query_count BETWEEN 0 AND 10000 "
            "AND exact_top_k BETWEEN 0 AND 1000 "
            "AND exact_overlap_count BETWEEN 0 AND 10000000 "
            "AND exact_expected_count BETWEEN 0 AND 10000000 "
            "AND exact_overlap_count<=exact_expected_count "
            "AND exact_expected_count<=exact_query_count*exact_top_k "
            "AND hnsw_ef_search BETWEEN 1 AND 1000 "
            "AND hnsw_iterative_scan IN ('off','strict_order','relaxed_order') "
            "AND minimum_recall_basis_points BETWEEN 1 AND 10000 "
            "AND observed_recall_basis_points BETWEEN 0 AND 10000",
            name="ck_rag_index_validations__probe",
        ),
        CheckConstraint(
            "(validation_state='PASSED' AND error_code IS NULL "
            "AND available_record_count=source_chunk_count "
            "AND missing_record_count=0 AND extra_record_count=0 "
            "AND duplicate_record_count=0 AND invalid_record_count=0 "
            "AND succeeded_batch_count=expected_batch_count "
            "AND hnsw_catalog_fingerprint IS NOT NULL "
            "AND hnsw_plan_observed AND exact_plan_observed "
            "AND hnsw_ef_search=200 AND hnsw_iterative_scan='strict_order' "
            "AND exact_query_count>0 AND exact_top_k>0 "
            "AND exact_expected_count>0 AND plan_fingerprint IS NOT NULL "
            "AND observed_recall_basis_points>=minimum_recall_basis_points) OR "
            "(validation_state='FAILED' "
            "AND error_code ~ '^RAG_[A-Z0-9_]{1,59}$')",
            name="ck_rag_index_validations__result",
        ),
        CheckConstraint(
            "created_xid>0 AND isfinite(completed_at)",
            name="ck_rag_index_validations__history",
        ),
        Index(
            "ix_rag_index_validations__project_result", "project_id",
            "validation_state", "completed_at", "embedding_index_validation_id",
        ),
    )

    embedding_index_validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_build_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    source_chunk_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    missing_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extra_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duplicate_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    invalid_record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_batch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded_batch_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_snapshot_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    build_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    record_set_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    validation_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    hnsw_index_name: Mapped[str] = mapped_column(Text, nullable=False)
    hnsw_catalog_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    hnsw_plan_observed: Mapped[bool] = mapped_column(nullable=False)
    exact_plan_observed: Mapped[bool] = mapped_column(nullable=False)
    hnsw_ef_search: Mapped[int] = mapped_column(Integer, nullable=False)
    hnsw_iterative_scan: Mapped[str] = mapped_column(Text, nullable=False)
    exact_query_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_overlap_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exact_expected_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    minimum_recall_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_recall_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    validation_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    validation_state: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    validated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class EmbeddingIndexQualityResultRow(Base):
    """Immutable held-out business-quality result; no query or answer body."""

    __tablename__ = "rag_embedding_index_quality_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["embedding_index_id"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_quality__index", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["technical_validation_ref"],
            ["plm.rag_embedding_index_validations.embedding_index_validation_id"],
            name="fk_rag_index_quality__technical_validation", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_quality__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["embedding_model_ref"], ["plm.ai_models.ai_model_id"],
            name="fk_rag_index_quality__model", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["evaluated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_quality__evaluator", ondelete="NO ACTION",
        ),
        UniqueConstraint(
            "embedding_index_id", "dataset_fingerprint", "evaluation_policy_ref",
            name="uq_rag_index_quality__index_dataset_policy",
        ),
        UniqueConstraint("dataset_fingerprint", name="uq_rag_index_quality__dataset"),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_quality__scope_project",
        ),
        CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "dataset_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,255}$' AND "
            "evaluation_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_rag_index_quality__refs",
        ),
        CheckConstraint(
            "octet_length(source_snapshot_fingerprint)=32 AND "
            "octet_length(dataset_fingerprint)=32 AND "
            "octet_length(isolation_attestation_fingerprint)=32 AND "
            "octet_length(evaluation_artifact_fingerprint)=32",
            name="ck_rag_index_quality__fingerprints",
        ),
        CheckConstraint(
            "dataset_case_count BETWEEN 50 AND 10000 AND "
            "classification_correct_count BETWEEN 0 AND dataset_case_count AND "
            "exact_citation_correct_count BETWEEN 0 AND dataset_case_count AND "
            "minimum_classification_basis_points=9000 AND "
            "minimum_exact_citation_basis_points=9800 AND "
            "classification_basis_points="
            "(classification_correct_count::bigint*10000/dataset_case_count) AND "
            "exact_citation_basis_points="
            "(exact_citation_correct_count::bigint*10000/dataset_case_count) AND "
            "out_of_scope_citation_count BETWEEN 0 AND dataset_case_count",
            name="ck_rag_index_quality__metrics",
        ),
        CheckConstraint(
            "(quality_state='PASSED' AND error_code IS NULL AND "
            "classification_basis_points>=minimum_classification_basis_points AND "
            "exact_citation_basis_points>=minimum_exact_citation_basis_points AND "
            "project_isolation_pass AND out_of_scope_citation_count=0 AND "
            "failure_closure_pass) OR (quality_state='FAILED' AND "
            "error_code ~ '^RAG_[A-Z0-9_]{1,59}$')",
            name="ck_rag_index_quality__result",
        ),
        CheckConstraint(
            "created_xid>0 AND isfinite(dataset_sealed_at) AND "
            "isfinite(completed_at) AND dataset_sealed_at<completed_at",
            name="ck_rag_index_quality__time",
        ),
        Index(
            "ix_rag_index_quality__index_time", "embedding_index_id",
            text("completed_at DESC"), text("quality_result_id DESC"),
        ),
    )

    quality_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    technical_validation_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    index_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_snapshot_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dataset_ref: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    isolation_attestation_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    evaluation_artifact_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    evaluation_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    classification_correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_citation_correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_classification_basis_points: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("9000"),
    )
    classification_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_exact_citation_basis_points: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("9800"),
    )
    exact_citation_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    project_isolation_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    out_of_scope_citation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_closure_pass: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_state: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    evaluated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dataset_sealed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class EmbeddingIndexActivationResultRow(Base):
    """Immutable first activation result and optional superseded Index."""

    __tablename__ = "rag_embedding_index_activation_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["embedding_index_id"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_activation__index", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["quality_result_ref"],
            ["plm.rag_embedding_index_quality_results.quality_result_id"],
            name="fk_rag_index_activation__quality", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["retired_index_ref"], ["plm.rag_embedding_indexes.embedding_index_id"],
            name="fk_rag_index_activation__retired", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_rag_index_activation__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["activated_by"], ["plm.auth_users.user_id"],
            name="fk_rag_index_activation__actor", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_rag_index_activation__audit", ondelete="NO ACTION",
        ),
        UniqueConstraint("embedding_index_id", name="uq_rag_index_activation__index"),
        UniqueConstraint("quality_result_ref", name="uq_rag_index_activation__quality"),
        UniqueConstraint("retired_index_ref", name="uq_rag_index_activation__retired"),
        UniqueConstraint("audit_event_id", name="uq_rag_index_activation__audit"),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL) OR "
            "(scope='PROJECT' AND project_id IS NOT NULL)",
            name="ck_rag_index_activation__scope_project",
        ),
        CheckConstraint(
            "index_purpose ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "embedding_index_id<>coalesce(retired_index_ref,"
            "'00000000-0000-0000-0000-000000000000'::uuid)",
            name="ck_rag_index_activation__refs",
        ),
        CheckConstraint(
            "expected_lock_version=2 AND lock_version=3 AND "
            "((retired_index_ref IS NULL AND "
            "retired_before_lock_version IS NULL AND retired_after_lock_version IS NULL) "
            "OR (retired_index_ref IS NOT NULL AND "
            "retired_before_lock_version>=3 AND "
            "retired_after_lock_version=retired_before_lock_version+1))",
            name="ck_rag_index_activation__versions",
        ),
        CheckConstraint("created_xid>0 AND isfinite(activated_at)",
                        name="ck_rag_index_activation__time"),
    )

    activation_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"),
    )
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quality_result_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    retired_index_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    index_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    activated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retired_before_lock_version: Mapped[int | None] = mapped_column(BigInteger)
    retired_after_lock_version: Mapped[int | None] = mapped_column(BigInteger)
    activated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
    )
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"),
    )


class RetrievalRunRow(Base):
    """Immutable initial RetrievalRun identity; later Owners own transitions."""

    __tablename__ = "rag_retrieval_runs"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_retrieval_runs__project"),
        ForeignKeyConstraint(["actor_ref"], ["plm.auth_users.user_id"],
                             name="fk_rag_retrieval_runs__actor"),
        ForeignKeyConstraint(["global_index_ref"],
                             ["plm.rag_embedding_indexes.embedding_index_id"],
                             name="fk_rag_retrieval_runs__global_index"),
        ForeignKeyConstraint(["project_index_ref"],
                             ["plm.rag_embedding_indexes.embedding_index_id"],
                             name="fk_rag_retrieval_runs__project_index"),
        ForeignKeyConstraint(["job_id"], ["plm.job_jobs.job_id"],
                             name="fk_rag_retrieval_runs__job"),
        UniqueConstraint("job_id", name="uq_rag_retrieval_runs__job"),
        CheckConstraint(
            "(scope='GLOBAL' AND project_id IS NULL AND global_index_ref IS NOT NULL "
            "AND project_index_ref IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL "
            "AND project_index_ref IS NOT NULL)",
            name="ck_rag_retrieval_runs__scope_project"),
        CheckConstraint(
            "octet_length(query_fingerprint)=32 AND "
            "octet_length(metadata_filter_fingerprint)=32 AND "
            "jsonb_typeof(metadata_filter)='object' AND "
            "(metadata_filter - ARRAY['document_category','source_type',"
            "'document_version_ref','effective_from','effective_to','business']::text[])="
            "'{}'::jsonb",
            name="ck_rag_retrieval_runs__query_filter"),
        CheckConstraint(
            "retrieval_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "rerank_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$'",
            name="ck_rag_retrieval_runs__policies"),
        CheckConstraint(
            "top_k BETWEEN 1 AND 100 AND "
            "rerank_state IN ('PENDING','NOT_APPLICABLE') AND "
            "egress_state IN ('PENDING','NOT_APPLICABLE') AND "
            "retrieval_state='RUNNING' AND jsonb_typeof(quality_flags)='array' AND "
            "NOT degraded AND error_code IS NULL AND completed_at IS NULL AND "
            "created_xid>0 AND lock_version=0 AND isfinite(created_at)",
            name="ck_rag_retrieval_runs__foundation_state"),
        Index("ix_rag_retrieval_runs__project_time", "project_id",
              text("created_at DESC"), text("retrieval_run_id DESC")),
    )

    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    query_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    metadata_filter: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metadata_filter_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    global_index_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    project_index_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retrieval_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    rerank_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    rerank_state: Mapped[str] = mapped_column(Text, nullable=False,
                                               server_default=text("'PENDING'"))
    egress_state: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_state: Mapped[str] = mapped_column(Text, nullable=False,
                                                  server_default=text("'RUNNING'"))
    quality_flags: Mapped[list] = mapped_column(JSONB, nullable=False,
                                                server_default=text("'[]'::jsonb"))
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                           server_default=text("false"))
    error_code: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"))


class RetrievalQueryContentRow(Base):
    """Ciphertext-only query body; plaintext is never stored in Run or Job."""

    __tablename__ = "rag_retrieval_query_contents"
    __table_args__ = (
        ForeignKeyConstraint(["retrieval_run_id"],
                             ["plm.rag_retrieval_runs.retrieval_run_id"],
                             name="fk_rag_retrieval_query_contents__run"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_retrieval_query_contents__project"),
        CheckConstraint(
            "octet_length(query_fingerprint)=32 AND "
            "octet_length(encrypted_payload) BETWEEN 17 AND 65536 AND "
            "jsonb_typeof(encryption_metadata)='object' AND "
            "encryption_metadata ? 'format' AND encryption_metadata ? 'nonce' AND "
            "key_provider_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,255}$'",
            name="ck_rag_retrieval_query_contents__cipher"),
        CheckConstraint(
            "plaintext_bytes BETWEEN 1 AND 16384 AND created_xid>0 AND "
            "isfinite(created_at) AND isfinite(retention_until) AND "
            "retention_until>created_at",
            name="ck_rag_retrieval_query_contents__retention"),
    )

    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    query_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
    key_provider_ref: Mapped[str] = mapped_column(Text, nullable=False)
    plaintext_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_until: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))


class RetrievalCandidateRow(Base):
    """Authorized immutable candidate snapshot; no vector or unbounded body."""

    __tablename__ = "rag_retrieval_candidates"
    __table_args__ = (
        ForeignKeyConstraint(["retrieval_run_id"],
                             ["plm.rag_retrieval_runs.retrieval_run_id"],
                             name="fk_rag_retrieval_candidates__run"),
        ForeignKeyConstraint(["run_project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_retrieval_candidates__run_project"),
        ForeignKeyConstraint(["candidate_project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_retrieval_candidates__candidate_project"),
        ForeignKeyConstraint(["embedding_index_id"],
                             ["plm.rag_embedding_indexes.embedding_index_id"],
                             name="fk_rag_retrieval_candidates__index"),
        ForeignKeyConstraint(["embedding_model_ref"], ["plm.ai_models.ai_model_id"],
                             name="fk_rag_retrieval_candidates__model"),
        ForeignKeyConstraint(["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
                             name="fk_rag_retrieval_candidates__chunk"),
        ForeignKeyConstraint(["document_version_ref"],
                             ["plm.doc_document_versions.document_version_id"],
                             name="fk_rag_retrieval_candidates__document_version"),
        ForeignKeyConstraint(["parse_result_ref"],
                             ["plm.doc_parse_result_refs.parse_result_ref_id"],
                             name="fk_rag_retrieval_candidates__parse_result"),
        UniqueConstraint("retrieval_run_id", "candidate_ordinal",
                         name="uq_rag_retrieval_candidates__ordinal"),
        UniqueConstraint("retrieval_run_id", "chunk_id",
                         name="uq_rag_retrieval_candidates__chunk"),
        CheckConstraint(
            "(candidate_scope='GLOBAL' AND candidate_project_id IS NULL) OR "
            "(candidate_scope='PROJECT' AND candidate_project_id IS NOT NULL)",
            name="ck_rag_retrieval_candidates__scope_project"),
        CheckConstraint(
            "source_type IN ('CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY',"
            "'REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER') AND "
            "jsonb_typeof(source_locator)='object' AND source_locator ? 'locator_type'",
            name="ck_rag_retrieval_candidates__source"),
        CheckConstraint(
            "retrieval_channel IN ('FTS','VECTOR','HYBRID','EXACT') AND "
            "candidate_ordinal BETWEEN 0 AND 9999 AND "
            "final_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            "octet_length(authorization_snapshot_fingerprint)=32 AND "
            "created_xid>0 AND isfinite(created_at)",
            name="ck_rag_retrieval_candidates__result"),
        Index("ix_rag_retrieval_candidates__run_rank", "retrieval_run_id",
              "candidate_ordinal"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    run_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    candidate_scope: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    embedding_index_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    embedding_model_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parse_result_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieval_channel: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    authorization_snapshot_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))


class RetrievalScorePartRow(Base):
    __tablename__ = "rag_retrieval_score_parts"
    __table_args__ = (
        ForeignKeyConstraint(["retrieval_run_id"],
                             ["plm.rag_retrieval_runs.retrieval_run_id"],
                             name="fk_rag_retrieval_score_parts__run"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_retrieval_score_parts__project"),
        ForeignKeyConstraint(["candidate_id"],
                             ["plm.rag_retrieval_candidates.candidate_id"],
                             name="fk_rag_retrieval_score_parts__candidate"),
        UniqueConstraint("candidate_id", "score_kind", "score_ordinal",
                         name="uq_rag_retrieval_score_parts__kind_ordinal"),
        CheckConstraint(
            "score_kind IN ('FTS','VECTOR','METADATA','SOURCE_WEIGHT','RERANK','FINAL') "
            "AND score_ordinal BETWEEN 0 AND 31 AND "
            "raw_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            "normalized_score_micros BETWEEN 0 AND 1000000 AND "
            "weight_micros BETWEEN 0 AND 1000000 AND "
            "weighted_score_micros BETWEEN -1000000000 AND 1000000000 AND "
            "score_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "created_xid>0 AND isfinite(created_at)",
            name="ck_rag_retrieval_score_parts__score"),
    )

    score_part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    score_kind: Mapped[str] = mapped_column(Text, nullable=False)
    score_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_score_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    normalized_score_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    weight_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    weighted_score_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    score_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))


class ContextBundleRow(Base):
    __tablename__ = "rag_context_bundles"
    __table_args__ = (
        ForeignKeyConstraint(["retrieval_run_id"],
                             ["plm.rag_retrieval_runs.retrieval_run_id"],
                             name="fk_rag_context_bundles__run"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_context_bundles__project"),
        UniqueConstraint("retrieval_run_id", "context_policy_ref",
                         name="uq_rag_context_bundles__run_policy"),
        UniqueConstraint("bundle_fingerprint",
                         name="uq_rag_context_bundles__fingerprint"),
        CheckConstraint(
            "context_policy_ref ~ '^[A-Za-z][A-Za-z0-9._:/-]{0,127}$' AND "
            "octet_length(bundle_fingerprint)=32 AND item_count BETWEEN 1 AND 100 AND "
            "token_budget BETWEEN 1 AND 1048576 AND token_count BETWEEN 1 AND token_budget "
            "AND created_xid>0 AND isfinite(created_at)",
            name="ck_rag_context_bundles__shape"),
    )

    context_bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    context_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    bundle_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))


class ContextItemRow(Base):
    __tablename__ = "rag_context_items"
    __table_args__ = (
        ForeignKeyConstraint(["context_bundle_id"],
                             ["plm.rag_context_bundles.context_bundle_id"],
                             name="fk_rag_context_items__bundle"),
        ForeignKeyConstraint(["retrieval_run_id"],
                             ["plm.rag_retrieval_runs.retrieval_run_id"],
                             name="fk_rag_context_items__run"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_rag_context_items__project"),
        ForeignKeyConstraint(["candidate_id"],
                             ["plm.rag_retrieval_candidates.candidate_id"],
                             name="fk_rag_context_items__candidate"),
        ForeignKeyConstraint(["chunk_id"], ["plm.rag_document_chunks.chunk_id"],
                             name="fk_rag_context_items__chunk"),
        ForeignKeyConstraint(["document_version_ref"],
                             ["plm.doc_document_versions.document_version_id"],
                             name="fk_rag_context_items__document_version"),
        UniqueConstraint("context_bundle_id", "item_ordinal",
                         name="uq_rag_context_items__ordinal"),
        UniqueConstraint("context_bundle_id", "candidate_id",
                         name="uq_rag_context_items__candidate"),
        CheckConstraint(
            "item_ordinal BETWEEN 0 AND 99 AND snippet_start>=0 AND "
            "snippet_end>snippet_start AND snippet_end-snippet_start<=8192 AND "
            "token_count BETWEEN 1 AND 16384 AND "
            "jsonb_typeof(source_locator)='object' AND source_locator ? 'locator_type' AND "
            "octet_length(snippet_fingerprint)=32 AND "
            "octet_length(access_snapshot_fingerprint)=32 AND "
            "created_xid>0 AND isfinite(created_at)",
            name="ck_rag_context_items__minimal"),
    )

    context_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    context_bundle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_locator: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snippet_start: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_snapshot_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    created_xid: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("txid_current()"))
