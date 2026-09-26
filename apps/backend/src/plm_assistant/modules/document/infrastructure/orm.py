"""DOC-03 FileObject metadata; file bytes stay outside PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_STATES = "'STAGED','AVAILABLE','FAILED','CLEANUP_PENDING','REMOVED','RESTRICTED'"


class FileObjectRow(Base):
    __tablename__ = "doc_file_objects"
    __table_args__ = (
        UniqueConstraint("file_object_id", "scope", "project_id",
                         name="uq_doc_file_objects__id_scope_project",
                         postgresql_nulls_not_distinct=True),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_doc_file_objects__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_doc_file_objects__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_doc_file_objects__updater", ondelete="NO ACTION"),
        CheckConstraint("(scope IN ('GLOBAL','DEPLOYMENT') AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_file_objects__scope_project"),
        CheckConstraint("""(usage_kind='DOCUMENT' AND owner_object_id IS NULL AND scope IN ('GLOBAL','PROJECT'))
 OR (usage_kind='AUDIT_EXPORT' AND owner_object_id IS NOT NULL
 AND owner_object_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND scope IN ('DEPLOYMENT','PROJECT') AND storage_class='PERSISTENT'
 AND sha256 IS NOT NULL AND size_bytes IS NOT NULL AND size_bytes BETWEEN 0 AND 134217728
 AND detected_mime IS NOT NULL AND detected_mime='application/x-ndjson'
 AND isfinite(created_at)
 AND (available_at IS NULL OR (isfinite(available_at) AND file_state IN ('AVAILABLE','RESTRICTED'))))""", name="ck_doc_file_objects__usage"),
        CheckConstraint("storage_class IN ('TEMPORARY','PERSISTENT')",
                        name="ck_doc_file_objects__storage_class"),
        CheckConstraint(f"file_state IN ({_STATES})", name="ck_doc_file_objects__state"),
        CheckConstraint("char_length(storage_locator) BETWEEN 1 AND 1024 AND left(storage_locator,1) <> '/' AND position('..' in storage_locator)=0 AND position(':' in storage_locator)=0 AND position(chr(92) in storage_locator)=0",
                        name="ck_doc_file_objects__locator"),
        CheckConstraint("char_length(original_name_metadata) BETWEEN 1 AND 255",
                        name="ck_doc_file_objects__name"),
        CheckConstraint("sha256 IS NULL OR octet_length(sha256)=32", name="ck_doc_file_objects__sha256"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_doc_file_objects__size"),
        CheckConstraint("detected_mime IS NULL OR char_length(detected_mime) BETWEEN 1 AND 255",
                        name="ck_doc_file_objects__mime"),
        CheckConstraint("failure_code IS NULL OR char_length(failure_code) BETWEEN 1 AND 64",
                        name="ck_doc_file_objects__failure"),
        CheckConstraint("lock_version >= 0", name="ck_doc_file_objects__version"),
        CheckConstraint("file_state NOT IN ('AVAILABLE','RESTRICTED') OR (sha256 IS NOT NULL AND size_bytes IS NOT NULL AND detected_mime IS NOT NULL AND available_at IS NOT NULL)",
                        name="ck_doc_file_objects__available_shape"),
        CheckConstraint("available_at IS NULL OR available_at >= created_at",
                        name="ck_doc_file_objects__available_time"),
        Index("ix_doc_file_objects__scope_project_state", "scope", "project_id", "file_state"),
    )

    file_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    usage_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DOCUMENT'"))
    owner_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    storage_class: Mapped[str] = mapped_column(Text, nullable=False)
    storage_locator: Mapped[str] = mapped_column(Text, nullable=False)
    original_name_metadata: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    detected_mime: Mapped[str | None] = mapped_column(Text)
    file_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'STAGED'"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    available_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    failure_code: Mapped[str | None] = mapped_column(Text)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class FileStateEventRow(Base):
    """Append-only state provenance; content and absolute paths are excluded."""

    __tablename__ = "doc_file_state_events"
    __table_args__ = (
        ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                             name="fk_doc_file_state_events__file", ondelete="NO ACTION"),
        ForeignKeyConstraint(["actor_user_id"], ["plm.auth_users.user_id"],
                             name="fk_doc_file_state_events__actor", ondelete="NO ACTION"),
        CheckConstraint(f"from_state IS NULL OR from_state IN ({_STATES})",
                        name="ck_doc_file_state_events__from"),
        CheckConstraint(f"to_state IN ({_STATES})", name="ck_doc_file_state_events__to"),
        CheckConstraint("reason_code IS NULL OR char_length(reason_code) BETWEEN 1 AND 64",
                        name="ck_doc_file_state_events__reason"),
        Index("ix_doc_file_state_events__file_created", "file_object_id", "created_at"),
    )

    file_state_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    file_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))


_DOCUMENT_CATEGORIES = "'CONTRACTUAL','PROJECT_RECORD','STANDARD_CAPABILITY','REFERENCE_MATERIAL','TEMPLATE','GENERATED_ARTIFACT','OTHER'"


class DocumentRow(Base):
    """DOC-01 stable identity and DOC-02 version pointers."""

    __tablename__ = "doc_documents"
    __table_args__ = (
        UniqueConstraint("document_id", "scope", "project_id",
                         name="uq_doc_documents__id_scope_project",
                         postgresql_nulls_not_distinct=True),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_doc_documents__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_doc_documents__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_doc_documents__updater", ondelete="NO ACTION"),
        ForeignKeyConstraint(["latest_version_ref", "document_id"],
                             ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"],
                             name="fk_doc_documents__latest_version", ondelete="NO ACTION",
                             use_alter=True),
        ForeignKeyConstraint(["effective_version_ref", "document_id"],
                             ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"],
                             name="fk_doc_documents__effective_version", ondelete="NO ACTION",
                             use_alter=True),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_documents__scope_project"),
        CheckConstraint(f"document_category IN ({_DOCUMENT_CATEGORIES})",
                        name="ck_doc_documents__category"),
        CheckConstraint("document_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
                        name="ck_doc_documents__state"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 255 AND title=btrim(title)",
                        name="ck_doc_documents__title"),
        CheckConstraint("char_length(original_display_name) BETWEEN 1 AND 255 AND original_display_name=btrim(original_display_name)",
                        name="ck_doc_documents__display_name"),
        CheckConstraint("document_subtype IS NULL OR (char_length(document_subtype) BETWEEN 1 AND 128 AND document_subtype=btrim(document_subtype))",
                        name="ck_doc_documents__subtype"),
        CheckConstraint("document_purpose IS NULL OR (char_length(document_purpose) BETWEEN 1 AND 255 AND document_purpose=btrim(document_purpose))",
                        name="ck_doc_documents__purpose"),
        CheckConstraint("document_category <> 'OTHER' OR (document_subtype IS NOT NULL AND document_purpose IS NOT NULL)",
                        name="ck_doc_documents__other_details"),
        CheckConstraint("document_category <> 'GENERATED_ARTIFACT' OR scope='PROJECT'",
                        name="ck_doc_documents__generated_scope"),
        CheckConstraint("lock_version >= 0", name="ck_doc_documents__version"),
        Index("ix_doc_documents__scope_project_state", "scope", "project_id", "document_state"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_category: Mapped[str] = mapped_column(Text, nullable=False)
    document_subtype: Mapped[str | None] = mapped_column(Text)
    document_purpose: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    original_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    document_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    latest_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    effective_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class DocumentVersionRow(Base):
    """DOC-02 immutable content snapshot, guarded by PostgreSQL triggers."""

    __tablename__ = "doc_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_doc_versions__document_no"),
        UniqueConstraint("document_version_id", "document_id",
                         name="uq_doc_versions__id_document"),
        UniqueConstraint("file_object_id", name="uq_doc_versions__file"),
        ForeignKeyConstraint(["document_id"], ["plm.doc_documents.document_id"],
                             name="fk_doc_versions__document", ondelete="NO ACTION"),
        ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                             name="fk_doc_versions__file", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_doc_versions__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["supersedes_version_ref", "document_id"],
                             ["plm.doc_document_versions.document_version_id", "plm.doc_document_versions.document_id"],
                             name="fk_doc_versions__supersedes", ondelete="NO ACTION"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_versions__scope_project"),
        CheckConstraint("version_no > 0", name="ck_doc_versions__number"),
        CheckConstraint("octet_length(content_sha256)=32", name="ck_doc_versions__sha256"),
        CheckConstraint("size_bytes >= 0", name="ck_doc_versions__size"),
        CheckConstraint("char_length(detected_mime) BETWEEN 1 AND 255",
                        name="ck_doc_versions__mime"),
        CheckConstraint("jsonb_typeof(source_metadata)='object'",
                        name="ck_doc_versions__source"),
        CheckConstraint("availability_state IN ('AVAILABLE','RESTRICTED','REVOKED')",
                        name="ck_doc_versions__state"),
        Index("ix_doc_versions__document_created", "document_id", "created_at"),
    )

    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detected_mime: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    availability_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'AVAILABLE'"))
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    integrity_checked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class DocumentVersionSourceRefRow(Base):
    """Append-only, non-path provenance for a committed content version."""

    __tablename__ = "doc_version_source_refs"
    __table_args__ = (
        UniqueConstraint("document_version_id", "ordinal",
                         name="uq_doc_version_sources__version_ordinal"),
        ForeignKeyConstraint(["document_version_id"],
                             ["plm.doc_document_versions.document_version_id"],
                             name="fk_doc_version_sources__version", ondelete="NO ACTION"),
        CheckConstraint("ordinal >= 0", name="ck_doc_version_sources__ordinal"),
        CheckConstraint("source_kind ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                        name="ck_doc_version_sources__kind"),
        CheckConstraint("(source_owner_module IS NULL AND source_object_type IS NULL AND source_object_id IS NULL AND source_version_id IS NULL) OR (source_owner_module IS NOT NULL AND source_object_type IS NOT NULL AND source_object_id IS NOT NULL)",
                        name="ck_doc_version_sources__ref_shape"),
        CheckConstraint("source_owner_module IS NULL OR source_owner_module ~ '^[a-z][a-z0-9_]{0,39}$'",
                        name="ck_doc_version_sources__owner"),
        CheckConstraint("source_object_type IS NULL OR source_object_type ~ '^[A-Z]{2,3}-[0-9]{2}$'",
                        name="ck_doc_version_sources__object_type"),
    )

    source_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_owner_module: Mapped[str | None] = mapped_column(Text)
    source_object_type: Mapped[str | None] = mapped_column(Text)
    source_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))


class ParseRecordRow(Base):
    """DOC-04 one retained parse attempt against an immutable content version."""

    __tablename__ = "doc_parse_records"
    __table_args__ = (
        UniqueConstraint("document_version_id", "parser_profile", "parser_version",
                         "attempt_no", name="uq_doc_parse_records__attempt"),
        UniqueConstraint("job_ref", "attempt_no", name="uq_doc_parse_records__job_attempt"),
        UniqueConstraint("result_ref", name="uq_doc_parse_records__result"),
        ForeignKeyConstraint(["document_version_id"],
                             ["plm.doc_document_versions.document_version_id"],
                             name="fk_doc_parse_records__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                             name="fk_doc_parse_records__job", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_doc_parse_records__project", ondelete="NO ACTION"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_parse_records__scope"),
        CheckConstraint("char_length(parser_profile) BETWEEN 1 AND 128 AND parser_profile=btrim(parser_profile)",
                        name="ck_doc_parse_records__profile"),
        CheckConstraint("char_length(parser_version) BETWEEN 1 AND 64 AND parser_version=btrim(parser_version)",
                        name="ck_doc_parse_records__parser_version"),
        CheckConstraint("attempt_no > 0 AND lock_version >= 0", name="ck_doc_parse_records__counters"),
        CheckConstraint("parse_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
                        name="ck_doc_parse_records__state"),
        CheckConstraint("completed_at IS NULL OR (started_at IS NULL OR completed_at >= started_at)",
                        name="ck_doc_parse_records__time"),
        CheckConstraint("result_sha256 IS NULL OR octet_length(result_sha256)=32",
                        name="ck_doc_parse_records__result_sha"),
        CheckConstraint("error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
                        name="ck_doc_parse_records__error"),
        CheckConstraint("(parse_state='PENDING' AND started_at IS NULL AND completed_at IS NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NULL AND retryable IS NULL) OR (parse_state='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NULL AND retryable IS NULL) OR (parse_state='SUCCEEDED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_ref IS NOT NULL AND result_sha256 IS NOT NULL AND error_code IS NULL AND retryable IS FALSE) OR (parse_state='FAILED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_ref IS NULL AND result_sha256 IS NULL AND error_code IS NOT NULL AND retryable IS NOT NULL) OR (parse_state='CANCELLED' AND completed_at IS NOT NULL AND result_ref IS NULL AND result_sha256 IS NULL AND retryable IS FALSE)",
                        name="ck_doc_parse_records__shape"),
        Index("ix_doc_parse_records__version_created", "document_version_id",
              "created_at", "parse_record_id"),
    )

    parse_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                       server_default=text("uuidv7()"))
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parser_profile: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(Text, nullable=False)
    job_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parse_state: Mapped[str] = mapped_column(Text, nullable=False,
                                            server_default=text("'PENDING'"))
    result_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    result_sha256: Mapped[bytes | None] = mapped_column(LargeBinary)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    error_code: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                 server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                              server_default=text("0"))


class ParseResultRefRow(Base):
    """Opaque, append-only metadata for an authorized structured parse result."""

    __tablename__ = "doc_parse_result_refs"
    __table_args__ = (
        UniqueConstraint("parse_record_id", name="uq_doc_parse_result_refs__record"),
        ForeignKeyConstraint(["parse_record_id"], ["plm.doc_parse_records.parse_record_id"],
                             name="fk_doc_parse_result_refs__record", ondelete="NO ACTION"),
        CheckConstraint("char_length(storage_locator) BETWEEN 1 AND 1024 AND left(storage_locator,1)<>'/' AND position('..' in storage_locator)=0 AND position(':' in storage_locator)=0 AND position(chr(92) in storage_locator)=0",
                        name="ck_doc_parse_result_refs__locator"),
        CheckConstraint("result_schema_version > 0 AND size_bytes >= 0",
                        name="ck_doc_parse_result_refs__numbers"),
        CheckConstraint("octet_length(sha256)=32", name="ck_doc_parse_result_refs__sha"),
    )

    parse_result_ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                           server_default=text("uuidv7()"))
    parse_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    storage_locator: Mapped[str] = mapped_column(Text, nullable=False)
    result_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                 server_default=text("statement_timestamp()"))


class UploadIntentRow(Base):
    """Private, expiring three-step upload control; never a content version."""

    __tablename__ = "doc_upload_intents"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_doc_upload_intents__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["actor_id"], ["plm.auth_users.user_id"],
                             name="fk_doc_upload_intents__actor", ondelete="NO ACTION"),
        ForeignKeyConstraint(["target_document_id"], ["plm.doc_documents.document_id"],
                             name="fk_doc_upload_intents__target_document", ondelete="NO ACTION"),
        ForeignKeyConstraint(["committed_document_id"], ["plm.doc_documents.document_id"],
                             name="fk_doc_upload_intents__committed_document", ondelete="NO ACTION"),
        ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                             name="fk_doc_upload_intents__file", ondelete="NO ACTION"),
        ForeignKeyConstraint(["document_version_id"], ["plm.doc_document_versions.document_version_id"],
                             name="fk_doc_upload_intents__version", ondelete="NO ACTION"),
        UniqueConstraint("token_digest", name="uq_doc_upload_intents__token_digest"),
        UniqueConstraint("file_object_id", name="uq_doc_upload_intents__file"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_upload_intents__scope_project"),
        CheckConstraint("state IN ('CREATED','CONTENT_READY','COMMITTED','ABORTED','EXPIRED')",
                        name="ck_doc_upload_intents__state"),
        CheckConstraint("octet_length(token_digest)=32", name="ck_doc_upload_intents__token_digest"),
        CheckConstraint("expires_at > created_at", name="ck_doc_upload_intents__expiry"),
        CheckConstraint("lock_version >= 0", name="ck_doc_upload_intents__version"),
        CheckConstraint("expected_size_bytes IS NULL OR expected_size_bytes >= 0",
                        name="ck_doc_upload_intents__size"),
        CheckConstraint("mime_hint IS NULL OR char_length(mime_hint) BETWEEN 1 AND 255",
                        name="ck_doc_upload_intents__mime"),
        CheckConstraint("char_length(purpose_code) BETWEEN 1 AND 64 AND purpose_code ~ '^[A-Z][A-Z0-9_]*$'",
                        name="ck_doc_upload_intents__purpose"),
        CheckConstraint("target_document_id IS NOT NULL OR (document_category IS NOT NULL AND title IS NOT NULL AND original_display_name IS NOT NULL)",
                        name="ck_doc_upload_intents__new_document"),
        CheckConstraint("target_document_id IS NULL OR (document_category IS NULL AND document_subtype IS NULL AND document_purpose IS NULL AND title IS NULL)",
                        name="ck_doc_upload_intents__existing_document"),
        CheckConstraint(f"document_category IS NULL OR document_category IN ({_DOCUMENT_CATEGORIES})",
                        name="ck_doc_upload_intents__category"),
        CheckConstraint("document_category IS DISTINCT FROM 'OTHER' OR (document_subtype IS NOT NULL AND document_purpose IS NOT NULL)",
                        name="ck_doc_upload_intents__other_details"),
        CheckConstraint("document_category IS DISTINCT FROM 'GENERATED_ARTIFACT' OR scope='PROJECT'",
                        name="ck_doc_upload_intents__generated_scope"),
        CheckConstraint("title IS NULL OR (char_length(title) BETWEEN 1 AND 255 AND title=btrim(title))",
                        name="ck_doc_upload_intents__title"),
        CheckConstraint("original_display_name IS NULL OR (char_length(original_display_name) BETWEEN 1 AND 255 AND original_display_name=btrim(original_display_name))",
                        name="ck_doc_upload_intents__name"),
        CheckConstraint("document_subtype IS NULL OR (char_length(document_subtype) BETWEEN 1 AND 128 AND document_subtype=btrim(document_subtype))",
                        name="ck_doc_upload_intents__subtype"),
        CheckConstraint("document_purpose IS NULL OR (char_length(document_purpose) BETWEEN 1 AND 255 AND document_purpose=btrim(document_purpose))",
                        name="ck_doc_upload_intents__document_purpose"),
        CheckConstraint("(state='CREATED' AND file_object_id IS NULL AND committed_document_id IS NULL AND document_version_id IS NULL) OR (state='CONTENT_READY' AND file_object_id IS NOT NULL AND committed_document_id IS NULL AND document_version_id IS NULL) OR (state='COMMITTED' AND file_object_id IS NOT NULL AND committed_document_id IS NOT NULL AND document_version_id IS NOT NULL) OR (state IN ('ABORTED','EXPIRED') AND committed_document_id IS NULL AND document_version_id IS NULL)",
                        name="ck_doc_upload_intents__state_shape"),
        Index("ix_doc_upload_intents__actor_state_expiry", "actor_id", "state", "expires_at"),
        Index("ix_doc_upload_intents__project_state_expiry", "project_id", "state", "expires_at"),
    )

    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_category: Mapped[str | None] = mapped_column(Text)
    document_subtype: Mapped[str | None] = mapped_column(Text)
    document_purpose: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    original_display_name: Mapped[str | None] = mapped_column(Text)
    purpose_code: Mapped[str] = mapped_column(Text, nullable=False)
    expected_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_hint: Mapped[str | None] = mapped_column(Text)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'CREATED'"))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    file_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    committed_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
