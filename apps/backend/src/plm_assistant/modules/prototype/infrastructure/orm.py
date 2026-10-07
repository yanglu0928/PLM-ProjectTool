"""PRT-01/PRT-02 identity, membership and NOT_REQUIRED decision schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class PrototypePackageRow(Base):
    __tablename__ = "prt_packages"
    __table_args__ = (
        UniqueConstraint(
            "prototype_package_id", "project_id", name="uq_prt_packages__id_project"
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_packages__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_packages__creator", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["updated_by"], ["plm.auth_users.user_id"],
            name="fk_prt_packages__updater", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_packages__name",
        ),
        CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_prt_packages__state",
        ),
        CheckConstraint("lock_version>=0", name="ck_prt_packages__lock"),
        Index(
            "ix_prt_packages__project_state", "project_id", "package_state",
            "prototype_package_id",
        ),
        {"schema": "plm"},
    )

    prototype_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    package_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class PrototypeRow(Base):
    __tablename__ = "prt_prototypes"
    __table_args__ = (
        UniqueConstraint(
            "prototype_id", "project_id", name="uq_prt_prototypes__id_project"
        ),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_prt_prototypes__project", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["plm.auth_users.user_id"],
            name="fk_prt_prototypes__creator", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["updated_by"], ["plm.auth_users.user_id"],
            name="fk_prt_prototypes__updater", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_prototypes__name",
        ),
        CheckConstraint(
            "prototype_state IN ('ACTIVE','NOT_REQUIRED','ARCHIVED','RESTRICTED')",
            name="ck_prt_prototypes__state",
        ),
        CheckConstraint("lock_version>=0", name="ck_prt_prototypes__lock"),
        Index(
            "ix_prt_prototypes__project_state", "project_id", "prototype_state",
            "prototype_id",
        ),
        {"schema": "plm"},
    )

    prototype_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prototype_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ACTIVE'")
    )
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class PrototypePackageMembershipRow(Base):
    __tablename__ = "prt_package_memberships"
    __table_args__ = (
        UniqueConstraint(
            "prototype_package_id", "prototype_id",
            name="uq_prt_package_memberships__package_prototype",
        ),
        ForeignKeyConstraint(
            ["prototype_package_id", "project_id"],
            ["plm.prt_packages.prototype_package_id", "plm.prt_packages.project_id"],
            name="fk_prt_package_memberships__package", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_package_memberships__prototype", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["added_by"], ["plm.auth_users.user_id"],
            name="fk_prt_package_memberships__adder", ondelete="NO ACTION",
        ),
        Index(
            "ix_prt_package_memberships__prototype", "prototype_id",
            "prototype_package_id",
        ),
        {"schema": "plm"},
    )

    prototype_package_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    prototype_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    prototype_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class PrototypePackageCreateResultRow(Base):
    """Immutable first-success Package view for idempotent replay."""

    __tablename__ = "prt_package_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prototype_package_id", "project_id"],
            ["plm.prt_packages.prototype_package_id", "plm.prt_packages.project_id"],
            name="fk_prt_package_create_results__package", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_package_create_results__name",
        ),
        {"schema": "plm"},
    )

    prototype_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )


class PrototypeCreateResultRow(Base):
    """Immutable first-success Prototype view for idempotent replay."""

    __tablename__ = "prt_prototype_create_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_prototype_create_results__prototype", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_prototype_create_results__name",
        ),
        {"schema": "plm"},
    )

    prototype_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )


class PrototypePackageCommandResultRow(Base):
    """Immutable result for PATCH and SET_MEMBERS."""

    __tablename__ = "prt_package_command_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prototype_package_id", "project_id"],
            ["plm.prt_packages.prototype_package_id", "plm.prt_packages.project_id"],
            name="fk_prt_package_command_results__package", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "operation IN ('PATCH','SET_MEMBERS')",
            name="ck_prt_package_command_results__operation",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_package_command_results__name",
        ),
        CheckConstraint(
            "package_state IN ('ACTIVE','ARCHIVED','RESTRICTED')",
            name="ck_prt_package_command_results__state",
        ),
        CheckConstraint("lock_version>0", name="ck_prt_package_command_results__version"),
        {"schema": "plm"},
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prototype_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
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


class PrototypeCommandResultRow(Base):
    """Immutable result for Prototype identity PATCH and ARCHIVE."""

    __tablename__ = "prt_prototype_command_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_prototype_command_results__prototype", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "operation IN ('PATCH','ARCHIVE')",
            name="ck_prt_prototype_command_results__operation",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_prototype_command_results__name",
        ),
        CheckConstraint(
            "prototype_state IN ('ACTIVE','ARCHIVED')",
            name="ck_prt_prototype_command_results__state",
        ),
        CheckConstraint(
            "(operation='PATCH' AND prototype_state='ACTIVE') OR "
            "(operation='ARCHIVE' AND prototype_state='ARCHIVED')",
            name="ck_prt_prototype_command_results__shape",
        ),
        CheckConstraint("lock_version>0", name="ck_prt_prototype_command_results__version"),
        {"schema": "plm"},
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prototype_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prototype_state: Mapped[str] = mapped_column(Text, nullable=False)
    current_approved_version_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class PrototypeScopeDecisionRow(Base):
    """Immutable NOT_REQUIRED scope decision; its write Owner is installed in A03."""

    __tablename__ = "prt_scope_decisions"
    __table_args__ = (
        UniqueConstraint(
            "scope_decision_id", "prototype_id", "project_id",
            name="uq_prt_scope_decisions__id_prototype_project",
        ),
        UniqueConstraint(
            "prototype_id", name="uq_prt_scope_decisions__prototype"
        ),
        ForeignKeyConstraint(
            ["prototype_id", "project_id"],
            ["plm.prt_prototypes.prototype_id", "plm.prt_prototypes.project_id"],
            name="fk_prt_scope_decisions__prototype", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["confirmed_by"], ["plm.auth_users.user_id"],
            name="fk_prt_scope_decisions__confirmer", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["review_id"], ["plm.rvw_reviews.review_id"],
            name="fk_prt_scope_decisions__review", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["review_round_id"], ["plm.rvw_review_rounds.review_round_id"],
            name="fk_prt_scope_decisions__round", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "decision_type='NOT_REQUIRED'", name="ck_prt_scope_decisions__type"
        ),
        CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
            name="ck_prt_scope_decisions__reason",
        ),
        CheckConstraint(
            "char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
            name="ck_prt_scope_decisions__impact",
        ),
        CheckConstraint(
            "(review_id IS NULL AND review_round_id IS NULL) OR "
            "(review_id IS NOT NULL AND review_round_id IS NOT NULL)",
            name="ck_prt_scope_decisions__review_pair",
        ),
        CheckConstraint(
            "before_version>=0 AND after_version=before_version+1",
            name="ck_prt_scope_decisions__version",
        ),
        CheckConstraint(
            "octet_length(decision_fingerprint)=32",
            name="ck_prt_scope_decisions__fingerprint",
        ),
        {"schema": "plm"},
    )

    scope_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    prototype_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    decision_fingerprint: Mapped[bytes] = mapped_column(nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    before_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    after_version: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PrototypeScopeDecisionRequirementRefRow(Base):
    """Fixed Approved RequirementVersion candidate owned by a scope decision."""

    __tablename__ = "prt_scope_decision_requirement_refs"
    __table_args__ = (
        UniqueConstraint(
            "scope_decision_id", "requirement_version_id",
            name="uq_prt_scope_req_refs__decision_version",
        ),
        UniqueConstraint(
            "scope_decision_id", "ordinal",
            name="uq_prt_scope_req_refs__decision_ordinal",
        ),
        ForeignKeyConstraint(
            ["scope_decision_id", "prototype_id", "project_id"],
            [
                "plm.prt_scope_decisions.scope_decision_id",
                "plm.prt_scope_decisions.prototype_id",
                "plm.prt_scope_decisions.project_id",
            ],
            name="fk_prt_scope_req_refs__decision", ondelete="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["requirement_version_id", "requirement_id", "project_id"],
            [
                "plm.req_requirement_versions.requirement_version_id",
                "plm.req_requirement_versions.requirement_id",
                "plm.req_requirement_versions.project_id",
            ],
            name="fk_prt_scope_req_refs__requirement_version", ondelete="NO ACTION",
        ),
        CheckConstraint("ordinal>0", name="ck_prt_scope_req_refs__ordinal"),
        Index(
            "ix_prt_scope_req_refs__requirement_version", "requirement_version_id",
            "scope_decision_id",
        ),
        {"schema": "plm"},
    )

    scope_decision_requirement_ref_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    scope_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    prototype_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class PrototypeScopeDecisionResultRow(Base):
    """Immutable first-success NOT_REQUIRED decision view."""

    __tablename__ = "prt_scope_decision_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scope_decision_id", "prototype_id", "project_id"],
            [
                "plm.prt_scope_decisions.scope_decision_id",
                "plm.prt_scope_decisions.prototype_id",
                "plm.prt_scope_decisions.project_id",
            ],
            name="fk_prt_scope_decision_results__decision", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255 AND name=btrim(name)",
            name="ck_prt_scope_decision_results__name",
        ),
        CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000 AND reason=btrim(reason)",
            name="ck_prt_scope_decision_results__reason",
        ),
        CheckConstraint(
            "char_length(impact) BETWEEN 1 AND 2000 AND impact=btrim(impact)",
            name="ck_prt_scope_decision_results__impact",
        ),
        CheckConstraint(
            "octet_length(decision_fingerprint)=32",
            name="ck_prt_scope_decision_results__fingerprint",
        ),
        CheckConstraint(
            "cardinality(requirement_version_refs)>0",
            name="ck_prt_scope_decision_results__requirements",
        ),
        CheckConstraint(
            "(review_id IS NULL AND review_round_id IS NULL) OR "
            "(review_id IS NOT NULL AND review_round_id IS NOT NULL)",
            name="ck_prt_scope_decision_results__review_pair",
        ),
        CheckConstraint("lock_version>0", name="ck_prt_scope_decision_results__version"),
        {"schema": "plm"},
    )

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope_decision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prototype_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    decision_fingerprint: Mapped[bytes] = mapped_column(nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_round_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requirement_version_refs: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
