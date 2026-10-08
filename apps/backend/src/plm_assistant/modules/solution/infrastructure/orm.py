"""Frozen SOL-02/SOL-04 project-scoped identity tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
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


class SolutionSectionRow(Base):
    __tablename__ = "sol_sections"
    __table_args__ = (
        UniqueConstraint("solution_section_id", "project_id", name="uq_sol_sections__id_project"),
        UniqueConstraint("solution_outline_id", "section_key", name="uq_sol_sections__outline_key"),
        ForeignKeyConstraint(["solution_outline_id", "project_id"],
                             ["plm.sol_outlines.solution_outline_id", "plm.sol_outlines.project_id"],
                             name="fk_sol_sections__outline_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_sol_sections__creator", ondelete="NO ACTION"),
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
