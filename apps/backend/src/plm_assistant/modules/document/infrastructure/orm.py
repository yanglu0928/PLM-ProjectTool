"""DOC-03 FileObject metadata; file bytes stay outside PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
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
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_doc_file_objects__scope_project"),
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
    """DOC-01 stable identity; version pointers stay NULL until DOC-02."""

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
        CheckConstraint("latest_version_ref IS NULL AND effective_version_ref IS NULL",
                        name="ck_doc_documents__pre_version_pointers"),
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
