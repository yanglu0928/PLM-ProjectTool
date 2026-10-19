"""Closed project Plan identity; version ownership follows in later WBS."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Text, UniqueConstraint, text
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
