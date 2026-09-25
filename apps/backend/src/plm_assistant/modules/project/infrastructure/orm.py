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


class ProjectMemberCreateResultRow(Base):
    """Immutable first-success projection for the member-create replay contract."""

    __tablename__ = "prj_member_create_results"
    __table_args__ = (
        ForeignKeyConstraint(["member_id", "project_id"],
                             ["plm.prj_project_members.project_member_id", "plm.prj_project_members.project_id"],
                             name="fk_prj_member_create_results__member_project", ondelete="NO ACTION"),
        CheckConstraint("role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_member_create_results__role"),
        CheckConstraint("char_length(user_display_name) BETWEEN 1 AND 255", name="ck_prj_member_create_results__user_name"),
        CheckConstraint("char_length(department_name) BETWEEN 1 AND 255", name="ck_prj_member_create_results__department_name"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_name: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)


class ProjectMemberStateResultRow(Base):
    """Immutable first-success MemberView for each state-command receipt."""

    __tablename__ = "prj_member_state_results"
    __table_args__ = (
        ForeignKeyConstraint(["member_id", "project_id"],
                             ["plm.prj_project_members.project_member_id", "plm.prj_project_members.project_id"],
                             name="fk_prj_member_state_results__member_project", ondelete="NO ACTION"),
        CheckConstraint("operation IN ('SUSPEND','RESUME','REMOVE')", name="ck_prj_member_state_results__operation"),
        CheckConstraint("role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_member_state_results__role"),
        CheckConstraint("(operation = 'SUSPEND' AND state = 'SUSPENDED') OR (operation = 'RESUME' AND state = 'ACTIVE') OR (operation = 'REMOVE' AND state = 'REMOVED')", name="ck_prj_member_state_results__state"),
        CheckConstraint("(state = 'REMOVED' AND ended_at IS NOT NULL) OR (state <> 'REMOVED' AND ended_at IS NULL)", name="ck_prj_member_state_results__ended_shape"),
        CheckConstraint("ended_at IS NULL OR ended_at >= effective_at", name="ck_prj_member_state_results__time"),
        CheckConstraint("lock_version > 0", name="ck_prj_member_state_results__version"),
        CheckConstraint("char_length(user_display_name) BETWEEN 1 AND 255", name="ck_prj_member_state_results__user_name"),
        CheckConstraint("char_length(department_name) BETWEEN 1 AND 255", name="ck_prj_member_state_results__department_name"),
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department_name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProjectMemberAssignmentHistoryRow(Base):
    __tablename__ = "prj_member_assignment_history"
    __table_args__ = (
        ForeignKeyConstraint(["project_member_id", "project_id"],
                             ["plm.prj_project_members.project_member_id", "plm.prj_project_members.project_id"],
                             name="fk_prj_assignment_history__member_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["actor_user_id"], ["plm.auth_users.user_id"],
                             name="fk_prj_assignment_history__actor", ondelete="NO ACTION"),
        ForeignKeyConstraint(["before_department_id", "project_id"],
                             ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
                             name="fk_prj_assignment_history__before_department", ondelete="NO ACTION"),
        ForeignKeyConstraint(["after_department_id", "project_id"],
                             ["plm.prj_departments.department_id", "plm.prj_departments.project_id"],
                             name="fk_prj_assignment_history__after_department", ondelete="NO ACTION"),
        UniqueConstraint("project_member_id", "after_version", name="uq_prj_assignment_history__member_version"),
        CheckConstraint("before_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_assignment_history__before_role"),
        CheckConstraint("after_role IN ('PROJECT_MANAGER','IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER')", name="ck_prj_assignment_history__after_role"),
        CheckConstraint("after_version = before_version + 1 AND before_version >= 0", name="ck_prj_assignment_history__version"),
        CheckConstraint("before_role <> after_role OR before_department_id <> after_department_id", name="ck_prj_assignment_history__changed"),
        Index("ix_prj_assignment_history__project_member", "project_id", "project_member_id", text("changed_at DESC")),
    )

    history_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before_role: Mapped[str] = mapped_column(Text, nullable=False)
    after_role: Mapped[str] = mapped_column(Text, nullable=False)
    before_department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    after_department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    before_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    after_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
