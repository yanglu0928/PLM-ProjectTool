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
