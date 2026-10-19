"""Closed project Plan identity; version ownership follows in later WBS."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, SmallInteger, Text, UniqueConstraint, text
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
    version_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'DRAFT'"))
    supersedes_version_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))


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
