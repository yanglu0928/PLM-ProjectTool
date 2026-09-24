"""Frozen PRJ-01/02/03 roots and cross-project database constraints."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class ProjectRow(Base):
    __tablename__ = "prj_projects"
    __table_args__ = (
        UniqueConstraint("project_code_normalized", name="uq_prj_projects__code_norm"),
        CheckConstraint("char_length(project_code) BETWEEN 1 AND 64", name="ck_prj_projects__code"),
        CheckConstraint("char_length(project_code_normalized) BETWEEN 1 AND 64 AND project_code_normalized = btrim(project_code_normalized)", name="ck_prj_projects__code_norm"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_prj_projects__name"),
        CheckConstraint("state IN ('ACTIVE','ARCHIVED')", name="ck_prj_projects__state"),
        CheckConstraint("lock_version >= 0", name="ck_prj_projects__lock_version"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_prj_projects__created_by", ondelete="NO ACTION"),
        Index("ix_prj_projects__state_updated", "state", text("updated_at DESC"), text("project_id DESC")),
        Index("ix_prj_projects__created_by", "created_by"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_code: Mapped[str] = mapped_column(Text, nullable=False)
    project_code_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class DepartmentRow(Base):
    __tablename__ = "prj_departments"
    __table_args__ = (
        UniqueConstraint("department_id", "project_id", name="uq_prj_departments__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_prj_departments__project", ondelete="NO ACTION"),
        CheckConstraint("char_length(department_code) BETWEEN 1 AND 64", name="ck_prj_departments__code"),
        CheckConstraint("char_length(department_code_normalized) BETWEEN 1 AND 64 AND department_code_normalized = btrim(department_code_normalized)", name="ck_prj_departments__code_norm"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 255", name="ck_prj_departments__name"),
        CheckConstraint("state IN ('ACTIVE','INACTIVE')", name="ck_prj_departments__state"),
        CheckConstraint("lock_version >= 0", name="ck_prj_departments__lock_version"),
        Index("uq_prj_departments__project_code_live", "project_id", "department_code_normalized", unique=True,
              postgresql_where=text("state = 'ACTIVE'")),
        Index("ix_prj_departments__project_state", "project_id", "state", text("updated_at DESC"), text("department_id DESC")),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_code: Mapped[str] = mapped_column(Text, nullable=False)
    department_code_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class ProjectMemberRow(Base):
    __tablename__ = "prj_project_members"
    __table_args__ = (
        UniqueConstraint("project_member_id", "project_id", name="uq_prj_members__id_project"),
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"], name="fk_prj_members__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["user_id"], ["plm.auth_users.user_id"], name="fk_prj_members__user", ondelete="NO ACTION"),
        ForeignKeyConstraint(["department_id", "project_id"], ["plm.prj_departments.department_id", "plm.prj_departments.project_id"], name="fk_prj_members__department_project", ondelete="NO ACTION"),
        CheckConstraint("project_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_members__role"),
        CheckConstraint("state IN ('ACTIVE','SUSPENDED','REMOVED')", name="ck_prj_members__state"),
        CheckConstraint("(state = 'REMOVED' AND ended_at IS NOT NULL) OR (state <> 'REMOVED' AND ended_at IS NULL)", name="ck_prj_members__ended_shape"),
        CheckConstraint("ended_at IS NULL OR ended_at >= effective_at", name="ck_prj_members__time"),
        CheckConstraint("lock_version >= 0", name="ck_prj_members__lock_version"),
        Index("uq_prj_members__user_active", "user_id", unique=True,
              postgresql_where=text("state <> 'REMOVED'")),
        Index("uq_prj_members__project_user_active", "project_id", "user_id", unique=True,
              postgresql_where=text("state <> 'REMOVED'")),
        Index("ix_prj_members__project_state", "project_id", "state", text("updated_at DESC"), text("project_member_id DESC")),
        Index("ix_prj_members__department_project", "department_id", "project_id"),
        Index("ix_prj_members__user", "user_id"),
    )

    project_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_role: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ACTIVE'"))
    effective_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
