"""EVD-01 fixed DocumentVersion evidence records; no public creation route."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_LOCATOR_TYPES = "'DOCUMENT','PAGE','TEXT_RANGE','SECTION','PARAGRAPH','TABLE_CELL','SHEET_RANGE','SLIDE_SHAPE','STRUCTURED_NODE'"
_ELIGIBILITY_STATES = "'CANDIDATE','ELIGIBLE','INELIGIBLE','REVOKED'"


class EvidenceRow(Base):
    __tablename__ = "evd_evidence_records"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_evd_evidence__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["document_version_id", "document_id"],
                             ["plm.doc_document_versions.document_version_id",
                              "plm.doc_document_versions.document_id"],
                             name="fk_evd_evidence__version_document", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_evd_evidence__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                             name="fk_evd_evidence__updater", ondelete="NO ACTION"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_evd_evidence__scope_project"),
        CheckConstraint(f"locator_type IN ({_LOCATOR_TYPES})", name="ck_evd_evidence__locator_type"),
        CheckConstraint("locator_schema_version=1", name="ck_evd_evidence__locator_version"),
        CheckConstraint("jsonb_typeof(locator_payload)='object' AND locator_payload ? 'locator_type' AND locator_payload->>'locator_type'=locator_type",
                        name="ck_evd_evidence__locator_payload"),
        CheckConstraint("octet_length(content_fingerprint)=32", name="ck_evd_evidence__fingerprint"),
        CheckConstraint("char_length(display_label) BETWEEN 1 AND 255 AND display_label=btrim(display_label)",
                        name="ck_evd_evidence__label"),
        CheckConstraint("display_excerpt IS NULL OR char_length(display_excerpt) BETWEEN 1 AND 500",
                        name="ck_evd_evidence__excerpt"),
        CheckConstraint(f"eligibility_state IN ({_ELIGIBILITY_STATES})", name="ck_evd_evidence__eligibility"),
        CheckConstraint("eligibility_reason IS NULL OR (char_length(eligibility_reason) BETWEEN 1 AND 1024 AND eligibility_reason=btrim(eligibility_reason))",
                        name="ck_evd_evidence__reason"),
        CheckConstraint("(eligibility_state='CANDIDATE' AND eligibility_reason IS NULL) OR (eligibility_state<>'CANDIDATE' AND eligibility_reason IS NOT NULL)",
                        name="ck_evd_evidence__reason_state"),
        CheckConstraint("lock_version >= 0", name="ck_evd_evidence__version"),
        Index("ix_evd_evidence__scope_project_created", "scope", "project_id", "created_at", "evidence_id"),
        Index("ix_evd_evidence__document_version", "document_version_id", "evidence_id"),
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                   server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    locator_type: Mapped[str] = mapped_column(Text, nullable=False)
    locator_schema_version: Mapped[int] = mapped_column(Integer, nullable=False,
                                                         server_default=text("1"))
    locator_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    display_label: Mapped[str] = mapped_column(Text, nullable=False)
    display_excerpt: Mapped[str | None] = mapped_column(Text)
    eligibility_state: Mapped[str] = mapped_column(Text, nullable=False,
                                                    server_default=text("'CANDIDATE'"))
    eligibility_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                 server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False,
                                                 server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False,
                                              server_default=text("0"))
