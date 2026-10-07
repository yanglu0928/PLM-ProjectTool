"""REQ-01/REQ-02 package and requirement identity schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
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
