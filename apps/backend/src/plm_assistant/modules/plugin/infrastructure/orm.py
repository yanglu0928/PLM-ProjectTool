"""Closed PLG-01 immutable package metadata foundations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class PluginPackageRow(Base):
    """One immutable developer-signed package identity and verification state."""

    __tablename__ = "plg_packages"
    __table_args__ = (
        UniqueConstraint(
            "plugin_package_id", "plugin_id_normalized",
            name="uq_plg_packages__id_plugin",
        ),
        UniqueConstraint(
            "plugin_id_normalized", "plugin_version",
            name="uq_plg_packages__plugin_version",
        ),
        CheckConstraint(
            "plugin_id_normalized = lower(plugin_id_normalized) "
            "AND plugin_id_normalized ~ '^[a-z0-9][a-z0-9._-]{1,127}$'",
            name="ck_plg_packages__plugin_id",
        ),
        CheckConstraint(
            "char_length(plugin_version) BETWEEN 1 AND 64 "
            "AND plugin_version = btrim(plugin_version)",
            name="ck_plg_packages__version",
        ),
        CheckConstraint(
            "octet_length(package_sha256) = 32",
            name="ck_plg_packages__hash",
        ),
        CheckConstraint(
            "octet_length(signature) BETWEEN 1 AND 4096",
            name="ck_plg_packages__signature",
        ),
        CheckConstraint(
            "jsonb_typeof(manifest_snapshot) = 'object' "
            "AND manifest_snapshot ? 'schema_version'",
            name="ck_plg_packages__manifest",
        ),
        CheckConstraint(
            "package_state IN ('IMPORTED','VERIFIED','REJECTED','REVOKED')",
            name="ck_plg_packages__state",
        ),
        CheckConstraint(
            "(package_state = 'IMPORTED' AND verified_at IS NULL) "
            "OR (package_state IN ('VERIFIED','REJECTED','REVOKED') "
            "AND verified_at IS NOT NULL)",
            name="ck_plg_packages__verification_time",
        ),
        CheckConstraint(
            "lock_version >= 0 AND isfinite(created_at) "
            "AND (verified_at IS NULL OR isfinite(verified_at))",
            name="ck_plg_packages__time_lock",
        ),
        Index(
            "ix_plg_packages__state_created",
            "package_state", "created_at", "plugin_package_id",
        ),
        {"schema": "plm"},
    )

    plugin_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    plugin_id_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    plugin_version: Mapped[str] = mapped_column(Text, nullable=False)
    package_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    manifest_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signer_key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    compatibility_policy_ref: Mapped[str] = mapped_column(Text, nullable=False)
    package_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'IMPORTED'")
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6)
    )
    verification_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )


class PluginManifestOperationRow(Base):
    """A structured operation declaration from an immutable package manifest."""

    __tablename__ = "plg_manifest_operations"
    __table_args__ = (
        UniqueConstraint(
            "plugin_package_id", "operation_id",
            name="uq_plg_manifest_operations__package_operation",
        ),
        ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_manifest_operations__package", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(operation_id) BETWEEN 1 AND 255 "
            "AND operation_id = btrim(operation_id)",
            name="ck_plg_manifest_operations__operation",
        ),
        CheckConstraint(
            "jsonb_typeof(output_types) = 'array' "
            "AND jsonb_array_length(output_types) > 0",
            name="ck_plg_manifest_operations__output_types",
        ),
        Index(
            "ix_plg_manifest_operations__operation",
            "operation_id", "plugin_package_id",
        ),
        {"schema": "plm"},
    )

    plugin_package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    operation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    output_types: Mapped[list] = mapped_column(JSONB, nullable=False)
    plugin_api_version: Mapped[str] = mapped_column(Text, nullable=False)


class PluginManifestDependencyRow(Base):
    """Normalized external dependency declaration; never contains credentials."""

    __tablename__ = "plg_manifest_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "plugin_package_id", "dependency_name",
            name="uq_plg_manifest_dependencies__package_name",
        ),
        ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_manifest_dependencies__package", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "char_length(dependency_name) BETWEEN 1 AND 255 "
            "AND dependency_name = btrim(dependency_name)",
            name="ck_plg_manifest_dependencies__name",
        ),
        CheckConstraint(
            "char_length(version_spec) BETWEEN 1 AND 255 "
            "AND version_spec = btrim(version_spec)",
            name="ck_plg_manifest_dependencies__version_spec",
        ),
        CheckConstraint(
            "dependency_kind IN ('PYTHON','OS','SYSTEM')",
            name="ck_plg_manifest_dependencies__kind",
        ),
        {"schema": "plm"},
    )

    dependency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dependency_name: Mapped[str] = mapped_column(Text, nullable=False)
    version_spec: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_kind: Mapped[str] = mapped_column(Text, nullable=False)


class PluginPackageVerificationRow(Base):
    """Append-only, minimized evidence for each package verification attempt."""

    __tablename__ = "plg_package_verifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_package_verifications__package", ondelete="NO ACTION",
        ),
        CheckConstraint(
            "verification_state IN ('PASSED','FAILED','INCOMPATIBLE')",
            name="ck_plg_package_verifications__state",
        ),
        CheckConstraint(
            "char_length(check_code) BETWEEN 1 AND 128 "
            "AND check_code = btrim(check_code)",
            name="ck_plg_package_verifications__check_code",
        ),
        CheckConstraint(
            "char_length(summary) BETWEEN 1 AND 2000 "
            "AND summary = btrim(summary)",
            name="ck_plg_package_verifications__summary",
        ),
        CheckConstraint(
            "evidence_fingerprint IS NULL OR octet_length(evidence_fingerprint) = 32",
            name="ck_plg_package_verifications__fingerprint",
        ),
        CheckConstraint(
            "isfinite(verified_at)",
            name="ck_plg_package_verifications__verified_at",
        ),
        Index(
            "ix_plg_package_verifications__package_time",
            "plugin_package_id", "verified_at", "verification_id",
        ),
        {"schema": "plm"},
    )

    verification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()")
    )
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    verification_state: Mapped[str] = mapped_column(Text, nullable=False)
    check_code: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    verified_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )
