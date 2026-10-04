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
