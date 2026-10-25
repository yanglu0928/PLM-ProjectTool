"""Closed project Plan identity; version ownership follows in later WBS."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKeyConstraint, Index, Integer, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class PlanRow(Base):
    __tablename__ = "pln_plans"
    __table_args__ = (
        UniqueConstraint("plan_id", "project_id", name="uq_pln_plans__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_pln_plans__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_pln_plans__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["current_approved_version_ref", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_plans__approved_version", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED", use_alter=True),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_pln_plans__name"),
        CheckConstraint("plan_state IN ('ACTIVE','ARCHIVED')", name="ck_pln_plans__state"),
        CheckConstraint("current_approved_version_ref IS NULL",
                        name="ck_pln_plans__approved_pointer_closed"),
        CheckConstraint("lock_version>=0", name="ck_pln_plans__lock"),
        Index("ix_pln_plans__project_state", "project_id", "plan_state", "plan_id"),
        {"schema": "plm"},
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class PlanCreateResultRow(Base):
    """Immutable initial PLAN_CREATE response, separate from mutable Plan metadata."""

    __tablename__ = "pln_plan_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "project_id"], ["plm.pln_plans.plan_id", "plm.pln_plans.project_id"],
            name="fk_pln_plan_create_results__plan", ondelete="NO ACTION",
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_pln_plan_create_results__name"),
        CheckConstraint("isfinite(created_at)", name="ck_pln_plan_create_results__created_at"),
        {"schema": "plm"},
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class PlanVersionRow(Base):
    """Closed PLN-02 version identity; content and Owner follow separately."""

    __tablename__ = "pln_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_version_id", "plan_id", "project_id",
                         name="uq_pln_plan_versions__id_plan_project"),
        UniqueConstraint("plan_id", "version_no", name="uq_pln_plan_versions__plan_no"),
        ForeignKeyConstraint(
            ["plan_id", "project_id"], ["plm.pln_plans.plan_id", "plm.pln_plans.project_id"],
            name="fk_pln_plan_versions__plan", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["supersedes_version_ref", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_plan_versions__supersedes", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["review_ref"], ["plm.rvw_reviews.review_id"],
                             name="fk_pln_plan_versions__review", ondelete="NO ACTION"),
        ForeignKeyConstraint(["review_round_ref"], ["plm.rvw_review_rounds.review_round_id"],
                             name="fk_pln_plan_versions__round", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_pln_plan_versions__creator", ondelete="NO ACTION"),
        CheckConstraint("version_no>0", name="ck_pln_plan_versions__number"),
        CheckConstraint(
            "version_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','SUPERSEDED','RESTRICTED')",
            name="ck_pln_plan_versions__state"),
        CheckConstraint("supersedes_version_ref IS NULL OR "
                        "supersedes_version_ref<>plan_version_id",
                        name="ck_pln_plan_versions__supersedes_not_self"),
        CheckConstraint("(review_ref IS NULL AND review_round_ref IS NULL) OR "
                        "(review_ref IS NOT NULL AND review_round_ref IS NOT NULL)",
                        name="ck_pln_plan_versions__review_pair"),
        CheckConstraint("isfinite(created_at)", name="ck_pln_plan_versions__created_at"),
        Index("ix_pln_plan_versions__plan_created", "plan_id", "created_at"),
        {"schema": "plm"},
    )

    plan_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(nullable=False)
    calendar_ref: Mapped[str | None] = mapped_column(Text)
    version_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'DRAFT'"))
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))


class PlanVersionExclusionRow(Base):
    """Fixed-target explicit exclusions owned by one immutable PlanVersion."""

    __tablename__ = "pln_version_exclusions"
    __table_args__ = (
        UniqueConstraint("exclusion_id", "plan_version_id", "plan_id", "project_id",
                         name="uq_pln_version_exclusions__id_version_plan_project"),
        UniqueConstraint("plan_version_id", "ordinal",
                         name="uq_pln_version_exclusions__version_ordinal"),
        UniqueConstraint("plan_version_id", "requirement_version_id",
                         name="uq_pln_version_exclusions__requirement"),
        UniqueConstraint("plan_version_id", "solution_outline_version_id",
                         name="uq_pln_version_exclusions__outline"),
        UniqueConstraint("plan_version_id", "solution_section_version_id",
                         name="uq_pln_version_exclusions__section"),
        UniqueConstraint("plan_version_id", "structured_solution_spec_id",
                         name="uq_pln_version_exclusions__spec"),
        ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_version_exclusions__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_pln_version_exclusions__requirement", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_pln_version_exclusions__outline", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_pln_version_exclusions__section", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id", "plm.sol_structured_specs.project_id",
             "plm.sol_structured_specs.spec_type"],
            name="fk_pln_version_exclusions__spec", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_pln_version_exclusions__ordinal"),
        CheckConstraint("target_kind IN ('REQUIREMENT_VERSION','SOLUTION_OUTLINE_VERSION',"
                        "'SOLUTION_SECTION_VERSION','STRUCTURED_SPEC_VERSION')",
                        name="ck_pln_version_exclusions__kind"),
        CheckConstraint("char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
                        name="ck_pln_version_exclusions__reason"),
        CheckConstraint("char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
                        name="ck_pln_version_exclusions__impact"),
        CheckConstraint(
            "(target_kind='REQUIREMENT_VERSION' AND requirement_id IS NOT NULL "
            "AND requirement_version_id IS NOT NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='SOLUTION_OUTLINE_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NOT NULL "
            "AND solution_outline_version_id IS NOT NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='SOLUTION_SECTION_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NOT NULL "
            "AND solution_section_version_id IS NOT NULL AND spec_series_id IS NULL "
            "AND structured_solution_spec_id IS NULL AND spec_type IS NULL) OR "
            "(target_kind='STRUCTURED_SPEC_VERSION' AND requirement_id IS NULL "
            "AND requirement_version_id IS NULL AND solution_outline_id IS NULL "
            "AND solution_outline_version_id IS NULL AND solution_section_id IS NULL "
            "AND solution_section_version_id IS NULL AND spec_series_id IS NOT NULL "
            "AND structured_solution_spec_id IS NOT NULL AND spec_type IS NOT NULL)",
            name="ck_pln_version_exclusions__typed_target"),
        Index("ix_pln_version_exclusions__target", "project_id", "target_kind",
              "plan_version_id"),
        {"schema": "plm"},
    )

    exclusion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requirement_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_outline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_outline_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_section_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    spec_series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    structured_solution_spec_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    spec_type: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)


class PlanWbsItemRow(Base):
    """Closed WBS identity scoped to one immutable PlanVersion."""

    __tablename__ = "pln_wbs_items"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "plan_version_id", "plan_id", "project_id",
                         name="uq_pln_wbs_items__id_version_plan_project"),
        UniqueConstraint("plan_version_id", "wbs_code",
                         name="uq_pln_wbs_items__version_code"),
        UniqueConstraint("plan_version_id", "parent_item_id", "ordinal",
                         name="uq_pln_wbs_items__parent_ordinal",
                         postgresql_nulls_not_distinct=True),
        ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_wbs_items__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["parent_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_items__parent", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        CheckConstraint("char_length(wbs_code) BETWEEN 1 AND 64 AND wbs_code=btrim(wbs_code)",
                        name="ck_pln_wbs_items__code"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_pln_wbs_items__name"),
        CheckConstraint("(parent_item_id IS NULL AND level=1) OR "
                        "(parent_item_id IS NOT NULL AND level BETWEEN 2 AND 6)",
                        name="ck_pln_wbs_items__level_root"),
        CheckConstraint("parent_item_id IS NULL OR parent_item_id<>wbs_item_id",
                        name="ck_pln_wbs_items__not_self"),
        CheckConstraint("ordinal>0", name="ck_pln_wbs_items__ordinal"),
        CheckConstraint("item_state IN "
                        "('NOT_STARTED','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')",
                        name="ck_pln_wbs_items__state"),
        ForeignKeyConstraint(
            ["owner_project_member_id", "project_id"],
            ["plm.prj_project_members.project_member_id",
             "plm.prj_project_members.project_id"],
            name="fk_pln_wbs_items__owner_member", ondelete="NO ACTION"),
        CheckConstraint("category_code IS NULL OR "
                        "(char_length(category_code) BETWEEN 1 AND 64 "
                        "AND category_code=btrim(category_code) "
                        "AND category_code ~ '^[A-Z][A-Z0-9_]*$')",
                        name="ck_pln_wbs_items__category"),
        CheckConstraint("planned_duration_minutes IS NULL OR planned_duration_minutes>=0",
                        name="ck_pln_wbs_items__planned_duration"),
        CheckConstraint("(planned_start_date IS NULL)=(planned_finish_date IS NULL)",
                        name="ck_pln_wbs_items__planned_date_pair"),
        CheckConstraint("planned_finish_date IS NULL OR planned_finish_date>=planned_start_date",
                        name="ck_pln_wbs_items__planned_date_order"),
        CheckConstraint("(actual_start_date IS NULL)=(actual_finish_date IS NULL)",
                        name="ck_pln_wbs_items__actual_date_pair"),
        CheckConstraint("actual_finish_date IS NULL OR actual_finish_date>=actual_start_date",
                        name="ck_pln_wbs_items__actual_date_order"),
        CheckConstraint("risk_summary IS NULL OR "
                        "(char_length(risk_summary) BETWEEN 1 AND 2000 "
                        "AND risk_summary=btrim(risk_summary))",
                        name="ck_pln_wbs_items__risk_summary"),
        CheckConstraint("explicit_exclusion_reason IS NULL OR "
                        "(char_length(explicit_exclusion_reason) BETWEEN 1 AND 2000 "
                        "AND explicit_exclusion_reason=btrim(explicit_exclusion_reason))",
                        name="ck_pln_wbs_items__exclusion_reason"),
        Index("ix_pln_wbs_items__parent_order", "plan_version_id", "parent_item_id",
              "ordinal", "wbs_item_id"),
        {"schema": "plm"},
    )

    wbs_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    wbs_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    item_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'NOT_STARTED'"))
    category_code: Mapped[str | None] = mapped_column(Text)
    owner_project_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_finish_date: Mapped[date | None] = mapped_column(Date)
    planned_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_finish_date: Mapped[date | None] = mapped_column(Date)
    risk_summary: Mapped[str | None] = mapped_column(Text)
    explicit_exclusion_reason: Mapped[str | None] = mapped_column(Text)


class PlanWbsSupportRoleRow(Base):
    """Ordered, bounded support-role snapshot for a WBS item."""

    __tablename__ = "pln_wbs_support_roles"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "support_role",
                         name="uq_pln_wbs_support_roles__item_role"),
        UniqueConstraint("wbs_item_id", "ordinal",
                         name="uq_pln_wbs_support_roles__item_ordinal"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_support_roles__item", ondelete="NO ACTION"),
        CheckConstraint("char_length(support_role) BETWEEN 1 AND 64 "
                        "AND support_role=btrim(support_role) "
                        "AND support_role ~ '^[A-Z][A-Z0-9_]*$'",
                        name="ck_pln_wbs_support_roles__role"),
        CheckConstraint("ordinal>0", name="ck_pln_wbs_support_roles__ordinal"),
        Index("ix_pln_wbs_support_roles__project_version", "project_id", "plan_version_id"),
        {"schema": "plm"},
    )

    support_role_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    support_role: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class PlanWbsConditionRow(Base):
    """Ordered entry/acceptance text owned by one immutable WBS item."""

    __tablename__ = "pln_wbs_conditions"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "condition_kind", "ordinal",
                         name="uq_pln_wbs_conditions__item_kind_ordinal"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_conditions__item", ondelete="NO ACTION"),
        CheckConstraint("condition_kind IN ('ENTRY','ACCEPTANCE')",
                        name="ck_pln_wbs_conditions__kind"),
        CheckConstraint("ordinal>0", name="ck_pln_wbs_conditions__ordinal"),
        CheckConstraint("char_length(condition_text) BETWEEN 1 AND 2000 "
                        "AND condition_text=btrim(condition_text)",
                        name="ck_pln_wbs_conditions__text"),
        Index("ix_pln_wbs_conditions__project_version", "project_id", "plan_version_id"),
        {"schema": "plm"},
    )

    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    condition_kind: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_text: Mapped[str] = mapped_column(Text, nullable=False)


class PlanWbsDependencyRow(Base):
    """Closed same-version FS edge; DAG validation belongs to the Owner."""

    __tablename__ = "pln_wbs_dependencies"
    __table_args__ = (
        UniqueConstraint("plan_version_id", "predecessor_item_id", "successor_item_id",
                         name="uq_pln_wbs_deps__version_edge"),
        ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_wbs_deps__version", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["predecessor_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_deps__predecessor", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["successor_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_wbs_deps__successor", ondelete="NO ACTION"),
        CheckConstraint("dependency_type='FS'", name="ck_pln_wbs_deps__type"),
        CheckConstraint("predecessor_item_id<>successor_item_id",
                        name="ck_pln_wbs_deps__not_self"),
        CheckConstraint("lag_unit IS NULL OR (char_length(lag_unit) BETWEEN 1 AND 32 "
                        "AND lag_unit=btrim(lag_unit))", name="ck_pln_wbs_deps__lag_unit"),
        CheckConstraint("lag_reason IS NULL OR (char_length(lag_reason) BETWEEN 1 AND 1000 "
                        "AND lag_reason=btrim(lag_reason))", name="ck_pln_wbs_deps__lag_reason"),
        CheckConstraint("lag=0 OR (lag_unit IS NOT NULL AND lag_reason IS NOT NULL)",
                        name="ck_pln_wbs_deps__lag_explicit"),
        Index("ix_pln_wbs_deps__out", "plan_version_id", "predecessor_item_id",
              "successor_item_id"),
        Index("ix_pln_wbs_deps__in", "plan_version_id", "successor_item_id",
              "predecessor_item_id"),
        {"schema": "plm"},
    )

    dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    predecessor_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    successor_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dependency_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'FS'"))
    lag: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    lag_unit: Mapped[str | None] = mapped_column(Text)
    lag_reason: Mapped[str | None] = mapped_column(Text)


class PlanMilestoneRow(Base):
    """Closed immutable-version milestone; Gate resolution follows in the Owner."""

    __tablename__ = "pln_milestones"
    __table_args__ = (
        UniqueConstraint("milestone_id", "plan_version_id", "plan_id", "project_id",
                         name="uq_pln_milestones__id_version_plan_project"),
        UniqueConstraint("plan_version_id", "name", name="uq_pln_milestones__version_name"),
        ForeignKeyConstraint(
            ["plan_version_id", "plan_id", "project_id"],
            ["plm.pln_plan_versions.plan_version_id", "plm.pln_plan_versions.plan_id",
             "plm.pln_plan_versions.project_id"],
            name="fk_pln_milestones__version", ondelete="NO ACTION"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 500 AND name=btrim(name)",
                        name="ck_pln_milestones__name"),
        CheckConstraint("isfinite(target_date)", name="ck_pln_milestones__target_date"),
        CheckConstraint("duration_days>=0", name="ck_pln_milestones__duration"),
        CheckConstraint("char_length(acceptance_rule) BETWEEN 1 AND 2000 "
                        "AND acceptance_rule=btrim(acceptance_rule)",
                        name="ck_pln_milestones__acceptance"),
        CheckConstraint("gate_ref IS NULL OR (char_length(gate_ref) BETWEEN 1 AND 128 "
                        "AND gate_ref=btrim(gate_ref))", name="ck_pln_milestones__gate_ref"),
        CheckConstraint("milestone_state IN ('PLANNED','ACHIEVED','CANCELLED')",
                        name="ck_pln_milestones__state"),
        Index("ix_pln_milestones__version_target", "plan_version_id", "target_date",
              "milestone_id"),
        {"schema": "plm"},
    )

    milestone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    acceptance_rule: Mapped[str] = mapped_column(Text, nullable=False)
    gate_ref: Mapped[str | None] = mapped_column(Text)
    milestone_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'PLANNED'"))


class PlanMilestoneItemRefRow(Base):
    """Closed same-version WBS membership of a milestone."""

    __tablename__ = "pln_milestone_item_refs"
    __table_args__ = (
        UniqueConstraint("milestone_id", "wbs_item_id",
                         name="uq_pln_milestone_items__milestone_item"),
        UniqueConstraint("milestone_id", "ordinal",
                         name="uq_pln_milestone_items__milestone_ordinal"),
        ForeignKeyConstraint(
            ["milestone_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_milestones.milestone_id", "plm.pln_milestones.plan_version_id",
             "plm.pln_milestones.plan_id", "plm.pln_milestones.project_id"],
            name="fk_pln_milestone_items__milestone", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_milestone_items__wbs", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_pln_milestone_items__ordinal"),
        Index("ix_pln_milestone_items__wbs", "plan_version_id", "wbs_item_id",
              "milestone_id"),
        {"schema": "plm"},
    )

    milestone_item_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    milestone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)


class PlanWbsRequirementRefRow(Base):
    """Closed WBS coverage of one fixed project RequirementVersion."""

    __tablename__ = "pln_item_requirement_refs"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "requirement_version_id",
                         name="uq_pln_item_requirements__item_version"),
        UniqueConstraint("wbs_item_id", "ordinal",
                         name="uq_pln_item_requirements__item_ordinal"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_requirements__wbs", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            ["plm.req_requirement_versions.requirement_version_id",
             "plm.req_requirement_versions.requirement_id",
             "plm.req_requirement_versions.project_id"],
            name="fk_pln_item_requirements__requirement", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_pln_item_requirements__ordinal"),
        Index("ix_pln_item_requirements__target", "project_id", "requirement_version_id",
              "plan_version_id"),
        {"schema": "plm"},
    )

    item_requirement_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)


class PlanWbsSolutionRefRow(Base):
    """Closed, strongly typed fixed Solution-version coverage of a WBS item."""

    __tablename__ = "pln_item_solution_refs"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "ordinal", name="uq_pln_item_solutions__item_ordinal"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_solutions__wbs", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["solution_outline_version_id", "solution_outline_id", "project_id"],
            ["plm.sol_outline_versions.solution_outline_version_id",
             "plm.sol_outline_versions.solution_outline_id",
             "plm.sol_outline_versions.project_id"],
            name="fk_pln_item_solutions__outline", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["solution_section_version_id", "solution_section_id", "project_id"],
            ["plm.sol_section_versions.solution_section_version_id",
             "plm.sol_section_versions.solution_section_id",
             "plm.sol_section_versions.project_id"],
            name="fk_pln_item_solutions__section", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type"],
            ["plm.sol_structured_specs.structured_solution_spec_id",
             "plm.sol_structured_specs.spec_series_id",
             "plm.sol_structured_specs.project_id", "plm.sol_structured_specs.spec_type"],
            name="fk_pln_item_solutions__spec", ondelete="NO ACTION"),
        CheckConstraint("ordinal>0", name="ck_pln_item_solutions__ordinal"),
        CheckConstraint(
            "(source_kind='OUTLINE' AND solution_outline_version_id IS NOT NULL "
            "AND solution_outline_id IS NOT NULL AND solution_section_version_id IS NULL "
            "AND solution_section_id IS NULL AND structured_solution_spec_id IS NULL "
            "AND spec_series_id IS NULL AND spec_type IS NULL) OR "
            "(source_kind='SECTION' AND solution_outline_version_id IS NULL "
            "AND solution_outline_id IS NULL AND solution_section_version_id IS NOT NULL "
            "AND solution_section_id IS NOT NULL AND structured_solution_spec_id IS NULL "
            "AND spec_series_id IS NULL AND spec_type IS NULL) OR "
            "(source_kind='STRUCTURED_SPEC' AND solution_outline_version_id IS NULL "
            "AND solution_outline_id IS NULL AND solution_section_version_id IS NULL "
            "AND solution_section_id IS NULL AND structured_solution_spec_id IS NOT NULL "
            "AND spec_series_id IS NOT NULL AND spec_type IS NOT NULL)",
            name="ck_pln_item_solutions__typed_target"),
        Index("uq_pln_item_solutions__outline", "wbs_item_id", "solution_outline_version_id",
              unique=True, postgresql_where=text("source_kind='OUTLINE'")),
        Index("uq_pln_item_solutions__section", "wbs_item_id", "solution_section_version_id",
              unique=True, postgresql_where=text("source_kind='SECTION'")),
        Index("uq_pln_item_solutions__spec", "wbs_item_id", "structured_solution_spec_id",
              unique=True, postgresql_where=text("source_kind='STRUCTURED_SPEC'")),
        Index("ix_pln_item_solutions__project_kind", "project_id", "source_kind",
              "plan_version_id"),
        {"schema": "plm"},
    )

    item_solution_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    solution_outline_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_outline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_section_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    solution_section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    structured_solution_spec_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    spec_series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    spec_type: Mapped[str | None] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(nullable=False)


class PlanWbsEvidenceRefRow(Base):
    """Closed fixed Evidence reference with database-proved Scope and Project."""

    __tablename__ = "pln_item_evidence_refs"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", "evidence_id",
                         name="uq_pln_item_evidence__item_evidence"),
        UniqueConstraint("wbs_item_id", "ordinal",
                         name="uq_pln_item_evidence__item_ordinal"),
        ForeignKeyConstraint(
            ["wbs_item_id", "plan_version_id", "plan_id", "project_id"],
            ["plm.pln_wbs_items.wbs_item_id", "plm.pln_wbs_items.plan_version_id",
             "plm.pln_wbs_items.plan_id", "plm.pln_wbs_items.project_id"],
            name="fk_pln_item_evidence__wbs", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["evidence_id", "source_scope"],
            ["plm.evd_evidence_records.evidence_id", "plm.evd_evidence_records.scope"],
            name="fk_pln_item_evidence__scope", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["evidence_id", "source_project_id"],
            ["plm.evd_evidence_records.evidence_id", "plm.evd_evidence_records.project_id"],
            name="fk_pln_item_evidence__project", ondelete="NO ACTION"),
        CheckConstraint(
            "(source_scope='GLOBAL' AND source_project_id IS NULL) OR "
            "(source_scope='PROJECT' AND source_project_id IS NOT NULL "
            "AND source_project_id=project_id)",
            name="ck_pln_item_evidence__scope_project"),
        CheckConstraint("ordinal>0", name="ck_pln_item_evidence__ordinal"),
        Index("ix_pln_item_evidence__target", "evidence_id", "project_id",
              "plan_version_id"),
        {"schema": "plm"},
    )

    item_evidence_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    wbs_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_scope: Mapped[str] = mapped_column(Text, nullable=False)
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ordinal: Mapped[int] = mapped_column(nullable=False)
