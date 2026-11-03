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



class PluginPackageImportStagingRow(Base):
    """Append-only async verification input metadata; ZIP bytes stay in private storage."""

    __tablename__ = "plg_package_import_stagings"
    __table_args__ = (
        CheckConstraint(
            "package_upload_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plg_package_import_stagings__id",
        ),
        CheckConstraint(
            "octet_length(package_sha256) = 32",
            name="ck_plg_package_import_stagings__hash",
        ),
        CheckConstraint(
            "package_size_bytes BETWEEN 1 AND 268435456",
            name="ck_plg_package_import_stagings__size",
        ),
        CheckConstraint(
            "octet_length(detached_signature) = 64",
            name="ck_plg_package_import_stagings__signature",
        ),
        CheckConstraint(
            "char_length(signer_key_ref) BETWEEN 1 AND 512 "
            "AND signer_key_ref = btrim(signer_key_ref)",
            name="ck_plg_package_import_stagings__signer_ref",
        ),
        CheckConstraint("isfinite(created_at)",
                        name="ck_plg_package_import_stagings__created_at"),
        Index("ix_plg_package_import_stagings__created",
              "created_at", "package_upload_id"),
        {"schema": "plm"},
    )

    package_upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
    )
    package_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    detached_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signer_key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"),
    )


class PluginInstallationRow(Base):
    """Deployment installation fact for one immutable developer package."""
    __tablename__ = "plg_installations"
    __table_args__ = (
        UniqueConstraint("plugin_installation_id", "plugin_package_id", "plugin_id_normalized",
                         name="uq_plg_installations__id_package_plugin"),
        ForeignKeyConstraint(["plugin_package_id", "plugin_id_normalized"],
            ["plm.plg_packages.plugin_package_id", "plm.plg_packages.plugin_id_normalized"],
            name="fk_plg_installations__package_plugin", ondelete="NO ACTION"),
        CheckConstraint("installation_state IN ('INSTALLED','ENABLED','DISABLED','INCOMPATIBLE','RETIRED')",
                         name="ck_plg_installations__state"),
        CheckConstraint("jsonb_typeof(validated_runtime_snapshot) = 'object'",
                         name="ck_plg_installations__runtime_snapshot"),
        CheckConstraint("(enabled_by IS NULL AND enabled_at IS NULL) OR "
                        "(enabled_by IS NOT NULL AND enabled_at IS NOT NULL)",
                        name="ck_plg_installations__enabled_actor_time"),
        CheckConstraint("installation_state <> 'ENABLED' OR "
                        "(enabled_by IS NOT NULL AND enabled_at IS NOT NULL)",
                        name="ck_plg_installations__enabled_state_actor"),
        CheckConstraint("lock_version >= 0 AND isfinite(created_at) AND isfinite(updated_at) "
                        "AND isfinite(installed_at) AND (enabled_at IS NULL OR isfinite(enabled_at)) "
                        "AND (retention_due_at IS NULL OR isfinite(retention_due_at))",
                        name="ck_plg_installations__time_lock"),
        Index("ix_plg_installations__state_created",
              "installation_state", "created_at", "plugin_installation_id"),
        {"schema": "plm"},
    )
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_id_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    installation_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INSTALLED'"))
    validated_runtime_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    installed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
        nullable=False, server_default=text("statement_timestamp()"))
    enabled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    enabled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
        nullable=False, server_default=text("statement_timestamp()"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
        nullable=False, server_default=text("statement_timestamp()"))
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retention_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True, precision=6))


class PluginEnabledOperationRow(Base):
    """An enabled operation selected from the installed package manifest."""
    __tablename__ = "plg_enabled_operations"
    __table_args__ = (
        ForeignKeyConstraint(["plugin_installation_id", "plugin_package_id", "plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id", "plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_enabled_operations__installation_package", ondelete="NO ACTION"),
        ForeignKeyConstraint(["plugin_package_id", "operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id", "plm.plg_manifest_operations.operation_id"],
            name="fk_plg_enabled_operations__manifest_operation", ondelete="NO ACTION"),
        CheckConstraint("char_length(operation_id) BETWEEN 1 AND 255 AND operation_id=btrim(operation_id)",
                        name="ck_plg_enabled_operations__operation"),
        Index("uq_plg_enabled_operations__plugin_operation", "plugin_id_normalized", "operation_id",
              unique=True),
        Index("ix_plg_enabled_operations__package", "plugin_package_id", "operation_id"),
        {"schema": "plm"},
    )
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_id_normalized: Mapped[str] = mapped_column(Text, nullable=False)


class PluginRuntimeValidationRow(Base):
    """Append-only host compatibility evidence for an installation."""
    __tablename__ = "plg_runtime_validations"
    __table_args__ = (
        ForeignKeyConstraint(["plugin_installation_id"],
            ["plm.plg_installations.plugin_installation_id"],
            name="fk_plg_runtime_validations__installation", ondelete="NO ACTION"),
        CheckConstraint("compatibility_state IN ('COMPATIBLE','INCOMPATIBLE')",
                        name="ck_plg_runtime_validations__state"),
        CheckConstraint("jsonb_typeof(runtime_snapshot) = 'object'",
                        name="ck_plg_runtime_validations__snapshot"),
        CheckConstraint("isfinite(validated_at)", name="ck_plg_runtime_validations__time"),
        Index("ix_plg_runtime_validations__installation_time",
              "plugin_installation_id", "validated_at", "runtime_validation_id"),
        {"schema": "plm"},
    )
    runtime_validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    compatibility_state: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
        nullable=False, server_default=text("statement_timestamp()"))



class PluginEnabledOperationHistoryRow(Base):
    """Immutable exact operation-level activation history linked to Audit."""
    __tablename__ = "plg_enabled_operation_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plugin_installation_id", "plugin_package_id", "plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id",
             "plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_enabled_operation_history__installation", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["plugin_package_id", "operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id",
             "plm.plg_manifest_operations.operation_id"],
            name="fk_plg_enabled_operation_history__manifest_operation", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["audit_event_id"], ["plm.aud_events.audit_event_id"],
            name="fk_plg_enabled_operation_history__audit_event", ondelete="NO ACTION"),
        CheckConstraint("transition IN ('ENABLED','DISABLED')",
                        name="ck_plg_enabled_operation_history__transition"),
        CheckConstraint("isfinite(changed_at)",
                        name="ck_plg_enabled_operation_history__changed_at"),
        Index("ix_plg_enabled_operation_history__plugin_operation_time",
              "plugin_id_normalized", "operation_id", "changed_at", "activation_history_id"),
        {"schema": "plm"},
    )
    activation_history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_id_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    transition: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
