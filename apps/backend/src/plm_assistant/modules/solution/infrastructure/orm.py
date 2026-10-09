"""Solution fixed-reference persistence foundations; writes stay closed."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Integer, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class SolutionOutlineRow(Base):
    __tablename__ = "sol_outlines"
    __table_args__ = (
        UniqueConstraint("solution_outline_id", "project_id", name="uq_sol_outlines__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_sol_outlines__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_outlines__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id", "plm.sol_outline_versions.project_id"],
            name="fk_sol_outlines__approved_version", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_sol_outlines__name"),
        CheckConstraint("outline_state IN ('ACTIVE','ARCHIVED')", name="ck_sol_outlines__state"),
        CheckConstraint("lock_version>=0", name="ck_sol_outlines__lock"),
        Index("ix_sol_outlines__project_state", "project_id", "outline_state", "solution_outline_id"),
        {"schema": "plm"},
    )

    solution_outline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    outline_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class SolutionOutlineCreateResultRow(Base):
    """Closed storage for the immutable first CREATE response."""

    __tablename__ = "sol_outline_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["solution_outline_id", "project_id"],
            ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
            name="fk_sol_outline_create_results__outline", ondelete="NO ACTION",
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_sol_outline_create_results__name"),
        CheckConstraint("isfinite(created_at)",
                        name="ck_sol_outline_create_results__created_at"),
        {"schema": "plm"},
    )

    solution_outline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False)


class SolutionSectionRow(Base):
    __tablename__ = "sol_sections"
    __table_args__ = (
        UniqueConstraint("solution_section_id", "project_id", name="uq_sol_sections__id_project"),
        UniqueConstraint("solution_section_id", "solution_outline_id", "project_id",
                         name="uq_sol_sections__id_outline_project"),
        UniqueConstraint("solution_outline_id", "section_key", name="uq_sol_sections__outline_key"),
        ForeignKeyConstraint(["solution_outline_id", "project_id"],
                             ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
                             name="fk_sol_sections__outline_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_sections__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
            name="fk_sol_sections__approved_version", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True,
        ),
        CheckConstraint("char_length(section_key) BETWEEN 1 AND 128 AND section_key=btrim(section_key)",
                        name="ck_sol_sections__key"),
        CheckConstraint("section_state IN ('ACTIVE','ARCHIVED')", name="ck_sol_sections__state"),
        CheckConstraint("lock_version>=0", name="ck_sol_sections__lock"),
        Index("ix_sol_sections__outline_state", "solution_outline_id", "section_state", "solution_section_id"),
        {"schema": "plm"},
    )

    solution_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_outline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    section_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class SolutionSectionCreateResultRow(Base):
    """Closed first-response storage; A02 does not install Section write Owner."""

    __tablename__ = "sol_section_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["solution_section_id", "solution_outline_id", "project_id"],
            ["plm.sol_sections.solution_section_id",
             "plm.sol_sections.solution_outline_id", "plm.sol_sections.project_id"],
            name="fk_sol_section_create_results__section", ondelete="NO ACTION",
        ),
        CheckConstraint("char_length(section_key) BETWEEN 1 AND 128 AND "
                        "section_key=btrim(section_key)",
                        name="ck_sol_section_create_results__key"),
        CheckConstraint("isfinite(created_at)",
                        name="ck_sol_section_create_results__created_at"),
        {"schema": "plm"},
    )

    solution_section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    solution_outline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class SolutionOutlineVersionRow(Base):
    __tablename__ = "sol_outline_versions"
    __table_args__ = (
        UniqueConstraint("solution_outline_version_id", "solution_outline_id", "project_id",
                         name="uq_sol_outline_versions__id_outline_project"),
        UniqueConstraint("solution_outline_id", "version_no", name="uq_sol_outline_versions__outline_no"),
        ForeignKeyConstraint(["solution_outline_id", "project_id"],
                             ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
                             name="fk_sol_outline_versions__outline", ondelete="NO ACTION"),
        ForeignKeyConstraint(["supersedes_version_ref", "solution_outline_id", "project_id"],
                             ["plm.sol_outline_versions.solution_outline_version_id",
                              "plm.sol_outline_versions.solution_outline_id",
                              "plm.sol_outline_versions.project_id"],
                             name="fk_sol_outline_versions__supersedes", ondelete="NO ACTION",
                             deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_sol_outline_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_sol_outline_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_outline_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_sol_outline_versions__number"),
        CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
                        name="ck_sol_outline_versions__state"),
        CheckConstraint("octet_length(content_fingerprint)=32", name="ck_sol_outline_versions__fingerprint"),
        CheckConstraint("jsonb_typeof(missing_declarations)='array' AND jsonb_typeof(conflict_declarations)='array'",
                        name="ck_sol_outline_versions__declarations"),
        CheckConstraint("declared_section_count BETWEEN 0 AND 100 AND declared_requirement_count BETWEEN 0 AND 500",
                        name="ck_sol_outline_versions__counts"),
        CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>solution_outline_version_id",
                        name="ck_sol_outline_versions__supersedes_not_self"),
        CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                        "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                        name="ck_sol_outline_versions__review_pair"),
        Index("ix_sol_outline_versions__outline_created", "solution_outline_id", "created_at"),
        {"schema": "plm"},
    )

    solution_outline_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_outline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    missing_declarations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    conflict_declarations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    declared_section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_requirement_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
                                                 nullable=False, server_default=text("statement_timestamp()"))


class SolutionOutlineSectionRow(Base):
    __tablename__ = "sol_outline_sections"
    __table_args__ = (
        UniqueConstraint("solution_outline_version_id", "ordinal", name="uq_sol_outline_sections__version_ordinal"),
        UniqueConstraint("solution_outline_version_id", "solution_section_id",
                         name="uq_sol_outline_sections__version_section"),
        ForeignKeyConstraint(["solution_outline_version_id", "solution_outline_id", "project_id"],
                             ["plm.sol_outline_versions.solution_outline_version_id",
                              "plm.sol_outline_versions.solution_outline_id", "plm.sol_outline_versions.project_id"],
                             name="fk_sol_outline_sections__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["solution_section_id", "solution_outline_id", "project_id"],
                             ["plm.sol_sections.solution_section_id", "plm.sol_sections.solution_outline_id",
                              "plm.sol_sections.project_id"],
                             name="fk_sol_outline_sections__section", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_outline_sections__ordinal"),
        {"schema": "plm"},
    )

    solution_outline_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_outline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_outline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class SolutionOutlineRequirementRefRow(Base):
    __tablename__ = "sol_outline_requirement_refs"
    __table_args__ = (
        UniqueConstraint("solution_outline_version_id", "ordinal", name="uq_sol_outline_requirements__version_ordinal"),
        UniqueConstraint("solution_outline_version_id", "requirement_version_id",
                         name="uq_sol_outline_requirements__version_requirement"),
        ForeignKeyConstraint(["solution_outline_version_id", "solution_outline_id", "project_id"],
                             ["plm.sol_outline_versions.solution_outline_version_id",
                              "plm.sol_outline_versions.solution_outline_id", "plm.sol_outline_versions.project_id"],
                             name="fk_sol_outline_requirements__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["requirement_version_id", "requirement_id", "project_id"],
                             ["plm.req_requirement_versions.requirement_version_id",
                              "plm.req_requirement_versions.requirement_id",
                              "plm.req_requirement_versions.project_id"],
                             name="fk_sol_outline_requirements__requirement", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_outline_requirements__ordinal"),
        Index("ix_sol_outline_requirements__target", "requirement_version_id", "solution_outline_version_id"),
        {"schema": "plm"},
    )

    solution_outline_requirement_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_outline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_outline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class SolutionSectionVersionRow(Base):
    __tablename__ = "sol_section_versions"
    __table_args__ = (
        UniqueConstraint("solution_section_version_id", "solution_section_id", "project_id",
                         name="uq_sol_section_versions__id_section_project"),
        UniqueConstraint("solution_section_id", "version_no", name="uq_sol_section_versions__section_no"),
        ForeignKeyConstraint(["solution_section_id", "project_id"],
                             ["plm.sol_sections.solution_section_id", "plm.sol_sections.project_id"],
                             name="fk_sol_section_versions__section", ondelete="NO ACTION"),
        ForeignKeyConstraint(["content_document_version_ref"],
                             ["plm.doc_document_versions.document_version_id"],
                             name="fk_sol_section_versions__document", ondelete="NO ACTION"),
        ForeignKeyConstraint(["supersedes_version_ref", "solution_section_id", "project_id"],
                             ["plm.sol_section_versions.solution_section_version_id",
                              "plm.sol_section_versions.solution_section_id",
                              "plm.sol_section_versions.project_id"],
                             name="fk_sol_section_versions__supersedes", ondelete="NO ACTION",
                             deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_sol_section_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_sol_section_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_section_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_sol_section_versions__number"),
        CheckConstraint("version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
                        name="ck_sol_section_versions__state"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 500 AND title=btrim(title)",
                        name="ck_sol_section_versions__title"),
        CheckConstraint("(content_document_version_ref IS NULL) <> (content_artifact_ref IS NULL)",
                        name="ck_sol_section_versions__content_xor"),
        CheckConstraint("octet_length(content_fingerprint)=32", name="ck_sol_section_versions__fingerprint"),
        CheckConstraint("jsonb_typeof(assumptions)='array' AND jsonb_typeof(exclusions)='array'",
                        name="ck_sol_section_versions__declarations"),
        CheckConstraint("declared_requirement_count BETWEEN 0 AND 500 AND declared_evidence_count BETWEEN 0 AND 500",
                        name="ck_sol_section_versions__counts"),
        CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>solution_section_version_id",
                        name="ck_sol_section_versions__supersedes_not_self"),
        CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                        "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                        name="ck_sol_section_versions__review_pair"),
        Index("ix_sol_section_versions__section_created", "solution_section_id", "created_at"),
        {"schema": "plm"},
    )

    solution_section_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_document_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_artifact_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    assumptions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    exclusions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    declared_requirement_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
                                                 nullable=False, server_default=text("statement_timestamp()"))


class SolutionSectionRequirementRefRow(Base):
    __tablename__ = "sol_section_requirement_refs"
    __table_args__ = (
        UniqueConstraint("solution_section_version_id", "ordinal", name="uq_sol_section_requirements__version_ordinal"),
        UniqueConstraint("solution_section_version_id", "requirement_version_id",
                         name="uq_sol_section_requirements__version_requirement"),
        ForeignKeyConstraint(["solution_section_version_id", "solution_section_id", "project_id"],
                             ["plm.sol_section_versions.solution_section_version_id",
                              "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
                             name="fk_sol_section_requirements__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["requirement_version_id", "requirement_id", "project_id"],
                             ["plm.req_requirement_versions.requirement_version_id",
                              "plm.req_requirement_versions.requirement_id", "plm.req_requirement_versions.project_id"],
                             name="fk_sol_section_requirements__requirement", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_section_requirements__ordinal"),
        Index("ix_sol_section_requirements__target", "requirement_version_id", "solution_section_version_id"),
        {"schema": "plm"},
    )
    solution_section_requirement_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_section_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class SolutionSectionEvidenceRefRow(Base):
    __tablename__ = "sol_section_evidence_refs"
    __table_args__ = (
        UniqueConstraint("solution_section_version_id", "ordinal", name="uq_sol_section_evidence__version_ordinal"),
        UniqueConstraint("solution_section_version_id", "evidence_id", name="uq_sol_section_evidence__version_evidence"),
        ForeignKeyConstraint(["solution_section_version_id", "solution_section_id", "project_id"],
                             ["plm.sol_section_versions.solution_section_version_id",
                              "plm.sol_section_versions.solution_section_id", "plm.sol_section_versions.project_id"],
                             name="fk_sol_section_evidence__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_sol_section_evidence__evidence", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_section_evidence__ordinal"),
        Index("ix_sol_section_evidence__target", "evidence_id", "solution_section_version_id"),
        {"schema": "plm"},
    )
    solution_section_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    solution_section_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    solution_section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class ReferenceSolutionRow(Base):
    __tablename__ = "sol_reference_solutions"
    __table_args__ = (
        UniqueConstraint("reference_solution_id", "scope", name="uq_sol_references__id_scope"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_sol_references__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_references__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["current_version_ref", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_references__current_version", ondelete="NO ACTION",
                             deferrable=True, initially="DEFERRED", use_alter=True),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_sol_references__scope"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
                        name="ck_sol_references__name"),
        CheckConstraint("eligibility_state IN ('REFERENCE_ONLY','ELIGIBLE','RESTRICTED','REVOKED')",
                        name="ck_sol_references__eligibility"),
        CheckConstraint("eligibility_reason IS NULL OR "
                        "(char_length(eligibility_reason) BETWEEN 1 AND 2000 AND eligibility_reason=btrim(eligibility_reason))",
                        name="ck_sol_references__reason"),
        CheckConstraint("lock_version>=0", name="ck_sol_references__lock"),
        Index("ix_sol_references__scope_project", "scope", "project_id", "eligibility_state"),
        {"schema": "plm"},
    )
    reference_solution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    eligibility_state: Mapped[str] = mapped_column(Text, nullable=False,
                                                   server_default=text("'REFERENCE_ONLY'"))
    eligibility_reason: Mapped[str | None] = mapped_column(Text)
    current_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
                                                 nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class ReferenceSolutionVersionRow(Base):
    __tablename__ = "sol_reference_versions"
    __table_args__ = (
        UniqueConstraint("reference_version_id", "reference_solution_id", "scope",
                         name="uq_sol_reference_versions__id_parent_scope"),
        UniqueConstraint("reference_solution_id", "version_no", name="uq_sol_reference_versions__parent_no"),
        ForeignKeyConstraint(["reference_solution_id", "scope"],
                             ["plm.sol_reference_solutions.reference_solution_id",
                              "plm.sol_reference_solutions.scope"],
                             name="fk_sol_reference_versions__parent", ondelete="NO ACTION"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_sol_reference_versions__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["supersedes_version_ref", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_reference_versions__supersedes", ondelete="NO ACTION",
                             deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_reference_versions__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["deidentification_confirmation_id", "source_fingerprint"],
                             ["plm.sol_reference_deidentification_confirmations.confirmation_id",
                              "plm.sol_reference_deidentification_confirmations.source_fingerprint"],
                             name="fk_sol_reference_versions__confirmation_source", ondelete="NO ACTION"),
        CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR "
                        "(scope='PROJECT' AND project_id IS NOT NULL)",
                        name="ck_sol_reference_versions__scope"),
        CheckConstraint("version_no>0", name="ck_sol_reference_versions__number"),
        CheckConstraint("version_state='DRAFT'", name="ck_sol_reference_versions__state"),
        CheckConstraint("octet_length(content_fingerprint)=32", name="ck_sol_reference_versions__fingerprint"),
        CheckConstraint("octet_length(source_fingerprint)=32",
                        name="ck_sol_reference_versions__source_fingerprint"),
        CheckConstraint("(scope='GLOBAL' AND deidentification_confirmation_id IS NOT NULL) OR "
                        "(scope='PROJECT' AND deidentification_confirmation_id IS NULL)",
                        name="ck_sol_reference_versions__confirmation_scope"),
        CheckConstraint("jsonb_typeof(applicability)='object'", name="ck_sol_reference_versions__applicability"),
        CheckConstraint("char_length(source_project_class) BETWEEN 1 AND 128 AND "
                        "source_project_class=btrim(source_project_class)",
                        name="ck_sol_reference_versions__source_class"),
        CheckConstraint("char_length(deidentification_class) BETWEEN 1 AND 128 AND "
                        "deidentification_class=btrim(deidentification_class)",
                        name="ck_sol_reference_versions__deidentification"),
        CheckConstraint("declared_document_count BETWEEN 1 AND 100 AND "
                        "declared_evidence_count BETWEEN 0 AND 500",
                        name="ck_sol_reference_versions__counts"),
        CheckConstraint("supersedes_version_ref IS NULL OR supersedes_version_ref<>reference_version_id",
                        name="ck_sol_reference_versions__supersedes_not_self"),
        Index("ix_sol_reference_versions__parent_created", "reference_solution_id", "created_at"),
        {"schema": "plm"},
    )
    reference_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    reference_solution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    applicability: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_project_class: Mapped[str] = mapped_column(Text, nullable=False)
    deidentification_class: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    deidentification_confirmation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    declared_document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
                                                 nullable=False, server_default=text("statement_timestamp()"))


class ReferenceSolutionReviseResultRow(Base):
    """Closed marker/snapshot for a revision's immutable first 201 result."""

    __tablename__ = "sol_reference_revise_results"
    __table_args__ = (
        ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_reference_revise_results__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["supersedes_version_ref", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_reference_revise_results__supersedes", ondelete="NO ACTION"),
        CheckConstraint("scope IN ('GLOBAL','PROJECT')", name="ck_sol_reference_revise_results__scope"),
        CheckConstraint("version_no>=2", name="ck_sol_reference_revise_results__number"),
        CheckConstraint("supersedes_version_ref<>reference_version_id",
                        name="ck_sol_reference_revise_results__not_self"),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_sol_reference_revise_results__content_fingerprint"),
        CheckConstraint("octet_length(source_fingerprint)=32",
                        name="ck_sol_reference_revise_results__source_fingerprint"),
        CheckConstraint("isfinite(created_at)", name="ck_sol_reference_revise_results__created_at"),
        CheckConstraint("result_lock_version>=1", name="ck_sol_reference_revise_results__lock"),
        {"schema": "plm"},
    )
    reference_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    reference_solution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    result_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ReferenceSolutionDocumentRefRow(Base):
    __tablename__ = "sol_reference_document_refs"
    __table_args__ = (
        UniqueConstraint("reference_version_id", "ordinal", name="uq_sol_reference_documents__version_ordinal"),
        UniqueConstraint("reference_version_id", "document_version_id",
                         name="uq_sol_reference_documents__version_document"),
        ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_reference_documents__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["document_version_id"], ["plm.doc_document_versions.document_version_id"],
                             name="fk_sol_reference_documents__document", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_reference_documents__ordinal"),
        Index("ix_sol_reference_documents__target", "document_version_id", "reference_version_id"),
        {"schema": "plm"},
    )
    reference_document_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    reference_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reference_solution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class ReferenceSolutionEvidenceRefRow(Base):
    __tablename__ = "sol_reference_evidence_refs"
    __table_args__ = (
        UniqueConstraint("reference_version_id", "ordinal", name="uq_sol_reference_evidence__version_ordinal"),
        UniqueConstraint("reference_version_id", "evidence_id", name="uq_sol_reference_evidence__version_evidence"),
        ForeignKeyConstraint(["reference_version_id", "reference_solution_id", "scope"],
                             ["plm.sol_reference_versions.reference_version_id",
                              "plm.sol_reference_versions.reference_solution_id",
                              "plm.sol_reference_versions.scope"],
                             name="fk_sol_reference_evidence__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
                             name="fk_sol_reference_evidence__evidence", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_sol_reference_evidence__ordinal"),
        Index("ix_sol_reference_evidence__target", "evidence_id", "reference_version_id"),
        {"schema": "plm"},
    )
    reference_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    reference_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reference_solution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class ReferenceDeidentificationConfirmationRow(Base):
    """GLOBAL attestation ledger; only one-time revocation may update history."""

    __tablename__ = "sol_reference_deidentification_confirmations"
    __table_args__ = (
        UniqueConstraint("confirmation_id", "source_fingerprint",
                         name="uq_sol_reference_deidentification__id_source"),
        ForeignKeyConstraint(["confirmed_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_reference_deidentification__actor", ondelete="NO ACTION"),
        CheckConstraint("octet_length(source_fingerprint)=32",
                        name="ck_sol_reference_deidentification__fingerprint"),
        CheckConstraint("char_length(source_project_class) BETWEEN 1 AND 128 AND "
                        "source_project_class=btrim(source_project_class)",
                        name="ck_sol_reference_deidentification__source_class"),
        CheckConstraint("char_length(deidentification_class) BETWEEN 1 AND 128 AND "
                        "deidentification_class=btrim(deidentification_class)",
                        name="ck_sol_reference_deidentification__class"),
        CheckConstraint("jsonb_typeof(applicability)='object'",
                        name="ck_sol_reference_deidentification__applicability"),
        CheckConstraint("attestation_statement='I_VERIFIED_DEIDENTIFICATION'",
                        name="ck_sol_reference_deidentification__statement"),
        CheckConstraint("confirmed_at<expires_at AND isfinite(confirmed_at) AND "
                        "isfinite(expires_at) AND (revoked_at IS NULL OR "
                        "(revoked_at>=confirmed_at AND isfinite(revoked_at)))",
                        name="ck_sol_reference_deidentification__time"),
        Index("ix_sol_reference_deidentification__source", "source_fingerprint",
              "expires_at", "confirmation_id"),
        {"schema": "plm"},
    )
    confirmation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    source_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_project_class: Mapped[str] = mapped_column(Text, nullable=False)
    deidentification_class: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    attestation_statement: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
