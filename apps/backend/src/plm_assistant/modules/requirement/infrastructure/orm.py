"""REQ-01/REQ-02 package and requirement identity schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class RequirementPackageRow(Base):
    __tablename__ = "req_packages"
    __table_args__ = (
        UniqueConstraint(
            "requirement_package_id",
            "project_id",
            name="uq_req_packages__id_project",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_req_packages__project",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_packages__creator",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["updated_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_packages__updater",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_req_packages__name",
        ),
        CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_req_packages__state",
        ),
        CheckConstraint("lock_version>=0", name="ck_req_packages__lock"),
        Index(
            "ix_req_packages__project_state",
            "project_id",
            "package_state",
            "requirement_package_id",
        ),
        {"schema": "plm"},
    )

    requirement_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    package_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class RequirementRow(Base):
    __tablename__ = "req_requirements"
    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "project_id",
            name="uq_req_requirements__id_project",
        ),
        UniqueConstraint(
            "project_id",
            "requirement_code_normalized",
            name="uq_req_requirements__project_code",
        ),
        ForeignKeyConstraint(
            ["project_id"],
            ["plm.prj_projects.project_id"],
            name="fk_req_requirements__project",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_requirements__creator",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["updated_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_requirements__updater",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "requirement_id", "project_id"],
            [
                "plm.req_requirement_versions.requirement_version_id",
                "plm.req_requirement_versions.requirement_id",
                "plm.req_requirement_versions.project_id",
            ],
            name="fk_req_requirements__approved_version",
            ondelete="NO ACTION",
            use_alter=True,
        ),
        CheckConstraint(
            "char_length(requirement_code) BETWEEN 1 AND 64 "
            "AND requirement_code=btrim(requirement_code)",
            name="ck_req_requirements__code",
        ),
        CheckConstraint(
            "requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
            name="ck_req_requirements__code_pattern",
        ),
        CheckConstraint(
            "char_length(requirement_code_normalized) BETWEEN 1 AND 64 "
            "AND requirement_code_normalized=btrim(requirement_code_normalized) "
            "AND requirement_code_normalized=upper(requirement_code)",
            name="ck_req_requirements__code_normalized",
        ),
        CheckConstraint(
            "requirement_state IN ('ACTIVE','DEFERRED','REJECTED','ARCHIVED')",
            name="ck_req_requirements__state",
        ),
        CheckConstraint("lock_version>=0", name="ck_req_requirements__lock"),
        Index(
            "ix_req_requirements__project_state",
            "project_id",
            "requirement_state",
            "requirement_id",
        ),
        {"schema": "plm"},
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_code: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_code_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'")
    )
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class RequirementPackageMembershipRow(Base):
    __tablename__ = "req_package_memberships"
    __table_args__ = (
        UniqueConstraint(
            "requirement_package_id",
            "requirement_id",
            name="uq_req_package_memberships__package_requirement",
        ),
        ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_memberships__package",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_package_memberships__requirement",
            ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["added_by"],
            ["plm.auth_users.user_id"],
            name="fk_req_package_memberships__adder",
            ondelete="NO ACTION",
        ),
        Index(
            "ix_req_package_memberships__requirement",
            "requirement_id",
            "requirement_package_id",
        ),
        {"schema": "plm"},
    )

    requirement_package_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )


class RequirementPackageCreateResultRow(Base):
    """Immutable first-success Package view for idempotent create replay."""

    __tablename__ = "req_package_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_create_results__package",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_req_package_create_results__name",
        ),
        {"schema": "plm"},
    )

    requirement_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )


class RequirementCreateResultRow(Base):
    """Immutable first-success Requirement view for idempotent create replay."""

    __tablename__ = "req_requirement_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_requirement_create_results__requirement",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
            name="ck_req_requirement_create_results__code",
        ),
        {"schema": "plm"},
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )


class RequirementPackageCommandResultRow(Base):
    """Immutable first-success Package projection for a mutation receipt."""

    __tablename__ = "req_package_command_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_package_id", "project_id"],
            ["plm.req_packages.requirement_package_id", "plm.req_packages.project_id"],
            name="fk_req_package_command_results__package",
            ondelete="NO ACTION",
        ),
        CheckConstraint(
            "operation IN ('PATCH','ADD','REMOVE')",
            name="ck_req_package_command_results__operation",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_req_package_command_results__name",
        ),
        CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_req_package_command_results__state",
        ),
        CheckConstraint("lock_version > 0", name="ck_req_package_command_results__version"),
        {"schema": "plm"},
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    requirement_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    package_state: Mapped[str] = mapped_column(Text, nullable=False)
    member_refs: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class RequirementStateDecisionRow(Base):
    """Immutable evidence-backed DEFER/REJECT decision fact."""

    __tablename__ = "req_requirement_state_decisions"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", "requirement_id", "project_id",
            name="uq_req_state_decisions__id_requirement_project",
        ),
        UniqueConstraint(
            "requirement_id", "after_version",
            name="uq_req_state_decisions__requirement_version",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_state_decisions__requirement", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["decided_by"], ["plm.auth_users.user_id"],
            name="fk_req_state_decisions__actor", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "decision_type IN ('DEFER','REJECT')",
            name="ck_req_state_decisions__type",
        ),
        CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
            name="ck_req_state_decisions__reason",
        ),
        CheckConstraint(
            "char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
            name="ck_req_state_decisions__impact",
        ),
        CheckConstraint(
            "before_version>=0 AND after_version=before_version+1",
            name="ck_req_state_decisions__version",
        ),
        {"schema": "plm"},
    )

    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    before_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    after_version: Mapped[int] = mapped_column(BigInteger, nullable=False)


class RequirementDecisionEvidenceRefRow(Base):
    """Immutable project-bound Evidence reference owned by a state decision."""

    __tablename__ = "req_requirement_decision_evidence_refs"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", "evidence_id",
            name="uq_req_decision_evidence_refs__decision_evidence",
        ),
        ForeignKeyConstraint(
            ["decision_id", "requirement_id", "project_id"],
            ["plm.req_requirement_state_decisions.decision_id",
             "plm.req_requirement_state_decisions.requirement_id",
             "plm.req_requirement_state_decisions.project_id"],
            name="fk_req_decision_evidence_refs__decision", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["evidence_id"], ["plm.evd_evidence_records.evidence_id"],
            name="fk_req_decision_evidence_refs__evidence", ondelete="NO ACTION",
        ),
        Index(
            "ix_req_decision_evidence_refs__evidence",
            "evidence_id", "decision_id",
        ),
        {"schema": "plm"},
    )

    decision_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class RequirementVersionRow(Base):
    """REQ-03 project-scoped immutable version primary."""

    __tablename__ = "req_requirement_versions"
    __table_args__ = (
        UniqueConstraint(
            "requirement_version_id", "requirement_id", "project_id",
            name="uq_req_versions__id_requirement_project",
        ),
        UniqueConstraint(
            "requirement_id", "version_no", name="uq_req_versions__requirement_no",
        ),
        ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_versions__requirement", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["supersedes_version_ref", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_versions__supersedes", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["review_ref"], ["plm.rvw_reviews.review_id"],
            name="fk_req_versions__review", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
            name="fk_req_versions__round", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_req_versions__creator", ondelete="NO ACTION",
        ),
        CheckConstraint("version_no>0", name="ck_req_versions__number"),
        CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED',"
            "'SUPERSEDED','RESTRICTED')", name="ck_req_versions__state",
        ),
        CheckConstraint(
            "title IS NULL OR (char_length(title) BETWEEN 1 AND 500 AND title=btrim(title))",
            name="ck_req_versions__title",
        ),
        CheckConstraint(
            "char_length(statement)>0 AND statement=btrim(statement)",
            name="ck_req_versions__statement",
        ),
        CheckConstraint(
            "char_length(rationale)>0 AND rationale=btrim(rationale)",
            name="ck_req_versions__rationale",
        ),
        CheckConstraint(
            "char_length(domain_name) BETWEEN 1 AND 255 AND domain_name=btrim(domain_name)",
            name="ck_req_versions__domain",
        ),
        CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')",
            name="ck_req_versions__priority",
        ),
        CheckConstraint(
            "risk IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_req_versions__risk",
        ),
        CheckConstraint(
            "requirement_classification IN ('STANDARD_FUNCTION','NONSTANDARD_FUNCTION',"
            "'DIFFERENCE','PENDING_CONFIRMATION')",
            name="ck_req_versions__classification",
        ),
        CheckConstraint("octet_length(content_fingerprint)=32",
                        name="ck_req_versions__fingerprint"),
        CheckConstraint(
            "declared_source_count>0 AND declared_acceptance_count>=0 "
            "AND declared_capability_count>=0 AND declared_assumption_count>=0 "
            "AND declared_exclusion_count>=0 AND declared_dependency_count>=0 "
            "AND declared_ai_task_count>=0", name="ck_req_versions__counts",
        ),
        CheckConstraint(
            "(review_ref IS NULL AND review_round_ref IS NULL) OR "
            "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
            name="ck_req_versions__review_shape",
        ),
        CheckConstraint(
            "supersedes_version_ref IS NULL OR "
            "supersedes_version_ref<>requirement_version_id",
            name="ck_req_versions__supersedes_not_self",
        ),
        Index("ix_req_versions__requirement_created", "requirement_id", "created_at"),
        Index("uq_req_versions__requirement_in_review", "requirement_id", unique=True,
              postgresql_where=text("version_state='IN_REVIEW'")),
        Index("uq_req_versions__requirement_approved", "requirement_id", unique=True,
              postgresql_where=text("version_state='APPROVED'")),
        {"schema": "plm"},
    )

    requirement_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'DRAFT'"))
    title: Mapped[str | None] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    domain_name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_classification: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    declared_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_acceptance_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_capability_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_assumption_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_exclusion_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_dependency_count: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_ai_task_count: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class RequirementSourceRow(Base):
    """Ordered fixed business source declared by a RequirementVersion."""

    __tablename__ = "req_sources"
    __table_args__ = (
        UniqueConstraint(
            "requirement_source_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_sources__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_sources__version_ordinal",
        ),
        UniqueConstraint(
            "requirement_version_id", "source_type", "source_object_id",
            name="uq_req_sources__version_source",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_sources__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_sources__ordinal"),
        CheckConstraint(
            "source_type IN ('APPROVED_SURVEY_CONCLUSION','CONFIRMED_HANDOVER',"
            "'HUMAN_DECISION','PROJECT_EVIDENCE')",
            name="ck_req_sources__type",
        ),
        CheckConstraint(
            "(source_type='CONFIRMED_HANDOVER' AND source_version_ref IS NOT NULL) OR "
            "(source_type<>'CONFIRMED_HANDOVER' AND source_version_ref IS NULL)",
            name="ck_req_sources__shape",
        ),
        Index("ix_req_sources__version_ordinal", "requirement_version_id", "ordinal"),
        {"schema": "plm"},
    )

    requirement_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class RequirementAcceptanceCriterionRow(Base):
    """Ordered, observable and verifiable acceptance condition."""

    __tablename__ = "req_acceptance_criteria"
    __table_args__ = (
        UniqueConstraint(
            "acceptance_criterion_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_acceptance__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_acceptance__version_ordinal",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_acceptance__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_acceptance__ordinal"),
        CheckConstraint(
            "char_length(observable_result) BETWEEN 1 AND 4000 "
            "AND observable_result=btrim(observable_result) "
            "AND char_length(verification_method) BETWEEN 1 AND 4000 "
            "AND verification_method=btrim(verification_method) "
            "AND char_length(required_data) BETWEEN 1 AND 4000 "
            "AND required_data=btrim(required_data) "
            "AND char_length(required_environment) BETWEEN 1 AND 4000 "
            "AND required_environment=btrim(required_environment) "
            "AND char_length(evidence_requirement) BETWEEN 1 AND 4000 "
            "AND evidence_requirement=btrim(evidence_requirement)",
            name="ck_req_acceptance__texts",
        ),
        Index("ix_req_acceptance__version_ordinal", "requirement_version_id", "ordinal"),
        {"schema": "plm"},
    )

    acceptance_criterion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    observable_result: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str] = mapped_column(Text, nullable=False)
    required_data: Mapped[str] = mapped_column(Text, nullable=False)
    required_environment: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_requirement: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementCapabilityAssessmentRow(Base):
    """Version-owned decision against one fixed GLOBAL capability item."""

    __tablename__ = "req_capability_assessments"
    __table_args__ = (
        UniqueConstraint(
            "capability_assessment_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_assessments__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_assessments__version_ordinal",
        ),
        UniqueConstraint(
            "requirement_version_id", "baseline_version_id", "capability_item_id",
            name="uq_req_assessments__version_capability",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_assessments__version", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["baseline_version_id", "capability_item_id"],
            ["plm.cap_items.baseline_version_id", "plm.cap_items.capability_item_id"],
            name="fk_req_assessments__capability", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["assessed_by"], ["plm.auth_users.user_id"],
            name="fk_req_assessments__assessor", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_assessments__ordinal"),
        CheckConstraint(
            "match_type IN ('DIRECT','PARTIAL','NONE','UNKNOWN')",
            name="ck_req_assessments__match",
        ),
        CheckConstraint(
            "confirmation_state IN ('CANDIDATE','CONFIRMED','REJECTED')",
            name="ck_req_assessments__confirmation",
        ),
        CheckConstraint(
            "(assessor_kind='HUMAN' AND assessed_by IS NOT NULL) OR "
            "(assessor_kind='AI_CANDIDATE' AND assessed_by IS NULL "
            "AND confirmation_state='CANDIDATE')",
            name="ck_req_assessments__assessor_shape",
        ),
        CheckConstraint(
            "char_length(fit_gap) BETWEEN 1 AND 4000 AND fit_gap=btrim(fit_gap) "
            "AND char_length(constraints_text) BETWEEN 1 AND 4000 "
            "AND constraints_text=btrim(constraints_text)",
            name="ck_req_assessments__texts",
        ),
        Index("ix_req_assessments__version_ordinal", "requirement_version_id", "ordinal"),
        Index("ix_req_assessments__capability", "baseline_version_id", "capability_item_id"),
        {"schema": "plm"},
    )

    capability_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    capability_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    match_type: Mapped[str] = mapped_column(Text, nullable=False)
    fit_gap: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_text: Mapped[str] = mapped_column(Text, nullable=False)
    assessor_kind: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    assessed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )
    confirmation_state: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementAssumptionRow(Base):
    __tablename__ = "req_assumptions"
    __table_args__ = (
        UniqueConstraint(
            "requirement_assumption_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_assumptions__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_assumptions__version_ordinal",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_assumptions__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_assumptions__ordinal"),
        CheckConstraint(
            "char_length(assumption_text) BETWEEN 1 AND 4000 "
            "AND assumption_text=btrim(assumption_text)",
            name="ck_req_assumptions__text",
        ),
        Index("ix_req_assumptions__version_ordinal", "requirement_version_id", "ordinal"),
        {"schema": "plm"},
    )

    requirement_assumption_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    assumption_text: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementExclusionRow(Base):
    __tablename__ = "req_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "requirement_exclusion_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_exclusions__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_exclusions__version_ordinal",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_exclusions__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_exclusions__ordinal"),
        CheckConstraint(
            "char_length(exclusion_text) BETWEEN 1 AND 4000 "
            "AND exclusion_text=btrim(exclusion_text)",
            name="ck_req_exclusions__text",
        ),
        Index("ix_req_exclusions__version_ordinal", "requirement_version_id", "ordinal"),
        {"schema": "plm"},
    )

    requirement_exclusion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusion_text: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementDependencyRow(Base):
    """Textual/external declaration, distinct from REQ-04 relation DAG."""

    __tablename__ = "req_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "requirement_dependency_id", "requirement_version_id", "requirement_id",
            "project_id", name="uq_req_dependencies__id_version_requirement_project",
        ),
        UniqueConstraint(
            "requirement_version_id", "ordinal", name="uq_req_dependencies__version_ordinal",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_req_dependencies__version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>=0", name="ck_req_dependencies__ordinal"),
        CheckConstraint(
            "char_length(dependency_text) BETWEEN 1 AND 4000 "
            "AND dependency_text=btrim(dependency_text)",
            name="ck_req_dependencies__text",
        ),
        Index("ix_req_dependencies__version_ordinal", "requirement_version_id", "ordinal"),
        {"schema": "plm"},
    )

    requirement_dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    dependency_text: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementCommandResultRow(Base):
    """Immutable first-success Requirement identity mutation projection."""

    __tablename__ = "req_requirement_command_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requirement_id", "project_id"],
            ["plm.req_requirements.requirement_id", "plm.req_requirements.project_id"],
            name="fk_req_command_results__requirement", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["decision_id", "requirement_id", "project_id"],
            ["plm.req_requirement_state_decisions.decision_id",
             "plm.req_requirement_state_decisions.requirement_id",
             "plm.req_requirement_state_decisions.project_id"],
            name="fk_req_command_results__decision", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "operation IN ('PATCH','DEFER','REJECT','ARCHIVE')",
            name="ck_req_command_results__operation",
        ),
        CheckConstraint(
            "requirement_code ~ '^[A-Za-z][A-Za-z0-9_.-]{0,63}$'",
            name="ck_req_command_results__code",
        ),
        CheckConstraint(
            "requirement_state IN ('ACTIVE','DEFERRED','REJECTED','ARCHIVED')",
            name="ck_req_command_results__state",
        ),
        CheckConstraint(
            "(operation='PATCH' AND requirement_state='ACTIVE' AND decision_id IS NULL "
            "AND reason IS NULL AND impact IS NULL AND cardinality(evidence_refs)=0) OR "
            "(operation='ARCHIVE' AND requirement_state='ARCHIVED' AND decision_id IS NULL "
            "AND reason IS NULL AND impact IS NULL AND cardinality(evidence_refs)=0) OR "
            "(operation='DEFER' AND requirement_state='DEFERRED' AND decision_id IS NOT NULL "
            "AND reason IS NOT NULL AND impact IS NOT NULL AND cardinality(evidence_refs)>0) OR "
            "(operation='REJECT' AND requirement_state='REJECTED' AND decision_id IS NOT NULL "
            "AND reason IS NOT NULL AND impact IS NOT NULL AND cardinality(evidence_refs)>0)",
            name="ck_req_command_results__shape",
        ),
        CheckConstraint("lock_version > 0", name="ck_req_command_results__version"),
        {"schema": "plm"},
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_code: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_state: Mapped[str] = mapped_column(Text, nullable=False)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
