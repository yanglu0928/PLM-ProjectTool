"""Closed PLG-01 immutable package metadata foundations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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



class PluginInstallationDisableResultRow(Base):
    """Immutable first response snapshot for an idempotent disable command."""
    __tablename__ = "plg_disable_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plugin_installation_id"],
            ["plm.plg_installations.plugin_installation_id"],
            name="fk_plg_disable_results__installation", ondelete="NO ACTION",
        ),
        CheckConstraint("expected_lock_version >= 0",
                        name="ck_plg_disable_results__expected_version"),
        CheckConstraint(
            "(changed AND result_lock_version = expected_lock_version + 1) OR "
            "(NOT changed AND result_lock_version = expected_lock_version)",
            name="ck_plg_disable_results__result_version",
        ),
        CheckConstraint("installation_state = 'DISABLED'",
                        name="ck_plg_disable_results__state"),
        CheckConstraint("isfinite(created_at)",
                        name="ck_plg_disable_results__created_at"),
        {"schema": "plm"},
    )
    disable_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expected_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result_lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    installation_state: Mapped[str] = mapped_column(Text, nullable=False)
    changed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))


class PluginExecutionRow(Base):
    """One project-scoped plugin attempt; persisted results remain staged until validated."""

    __tablename__ = "plg_executions"
    __table_args__ = (
        UniqueConstraint("plugin_execution_id", "project_id",
                         name="uq_plg_executions__id_project"),
        UniqueConstraint("plugin_execution_id", "output_request_id", "project_id",
                         name="uq_plg_executions__id_request_project"),
        UniqueConstraint("project_id", "idempotency_key",
                         name="uq_plg_executions__project_idempotency"),
        UniqueConstraint("job_id", name="uq_plg_executions__job"),
        ForeignKeyConstraint(
            ["project_id"], ["plm.prj_projects.project_id"],
            name="fk_plg_executions__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["output_request_id", "project_id"],
            ["plm.out_output_requests.output_request_id",
             "plm.out_output_requests.project_id"],
            name="fk_plg_executions__output_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["output_context_snapshot_id", "project_id"],
            ["plm.out_context_snapshots.context_snapshot_id",
             "plm.out_context_snapshots.project_id"],
            name="fk_plg_executions__context_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["plugin_installation_id", "plugin_package_id", "plugin_id_normalized"],
            ["plm.plg_installations.plugin_installation_id",
             "plm.plg_installations.plugin_package_id",
             "plm.plg_installations.plugin_id_normalized"],
            name="fk_plg_executions__installation_package", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["plugin_package_id", "operation_id"],
            ["plm.plg_manifest_operations.plugin_package_id",
             "plm.plg_manifest_operations.operation_id"],
            name="fk_plg_executions__manifest_operation", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["job_id"], ["plm.job_jobs.job_id"],
            name="fk_plg_executions__job", ondelete="NO ACTION"),
        CheckConstraint(
            "char_length(operation_id) BETWEEN 1 AND 255 "
            "AND operation_id = btrim(operation_id)",
            name="ck_plg_executions__operation"),
        CheckConstraint("attempt_no > 0",
                        name="ck_plg_executions__attempt"),
        CheckConstraint("octet_length(context_fingerprint) = 32",
                        name="ck_plg_executions__context_hash"),
        CheckConstraint(
            "execution_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_executions__state"),
        CheckConstraint("lock_version >= 0",
                        name="ck_plg_executions__lock_version"),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 200 "
            "AND idempotency_key = btrim(idempotency_key)",
            name="ck_plg_executions__idempotency"),
        CheckConstraint(
            "(execution_state='PENDING' AND started_at IS NULL AND completed_at IS NULL) OR "
            "(execution_state='RUNNING' AND started_at IS NOT NULL AND completed_at IS NULL) OR "
            "(execution_state IN ('SUCCEEDED','FAILED') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(execution_state='CANCELLED' AND completed_at IS NOT NULL)",
            name="ck_plg_executions__time_shape"),
        CheckConstraint(
            "(error_code IS NULL AND retryable IS NULL) OR "
            "(execution_state='FAILED' AND error_code IS NOT NULL AND retryable IS NOT NULL "
            "AND error_code ~ '^[A-Z][A-Z0-9_]{0,63}$')",
            name="ck_plg_executions__error_shape"),
        CheckConstraint(
            "(execution_state='SUCCEEDED' AND result_manifest_ref IS NOT NULL "
            "AND position(chr(92) in result_manifest_ref) = 0 "
            "AND result_fingerprint IS NOT NULL "
            "AND octet_length(result_fingerprint)=32) OR "
            "(execution_state<>'SUCCEEDED' AND result_manifest_ref IS NULL "
            "AND result_fingerprint IS NULL)",
            name="ck_plg_executions__result_shape"),
        CheckConstraint("isfinite(created_at)", name="ck_plg_executions__created_at"),
        CheckConstraint("retention_due_at IS NULL OR isfinite(retention_due_at)",
                        name="ck_plg_executions__retention_due_at"),
        CheckConstraint("started_at IS NULL OR isfinite(started_at)",
                        name="ck_plg_executions__started_at"),
        CheckConstraint("completed_at IS NULL OR isfinite(completed_at)",
                        name="ck_plg_executions__completed_at"),
        Index("ix_plg_executions__project_state_created",
              "project_id", "execution_state", "created_at", "plugin_execution_id"),
        {"schema": "plm"},
    )

    plugin_execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_context_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plugin_id_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    operation_id: Mapped[str] = mapped_column(Text, nullable=False)
    context_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    execution_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'PENDING'"))
    result_manifest_ref: Mapped[str | None] = mapped_column(Text)
    result_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary)
    error_code: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6))
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
    lock_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"))
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retention_due_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True, precision=6))


class PluginExecutionResultFileRow(Base):
    """Immutable reference to a project-scoped staged FileObject, never file bytes."""

    __tablename__ = "plg_execution_result_files"
    __table_args__ = (
        UniqueConstraint("plugin_execution_id", "project_id", "relative_name",
                         name="uq_plg_exec_result_files__execution_name"),
        UniqueConstraint("file_object_id", name="uq_plg_exec_result_files__file"),
        ForeignKeyConstraint(
            ["plugin_execution_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id", "plm.plg_executions.project_id"],
            name="fk_plg_exec_result_files__execution_project", ondelete="NO ACTION"),
        ForeignKeyConstraint(
            ["file_object_id", "file_scope", "project_id"],
            ["plm.doc_file_objects.file_object_id", "plm.doc_file_objects.scope",
             "plm.doc_file_objects.project_id"],
            name="fk_plg_exec_result_files__file_project", ondelete="NO ACTION"),
        CheckConstraint("file_scope = 'PROJECT'",
                        name="ck_plg_exec_result_files__scope"),
        CheckConstraint(
            "char_length(relative_name) BETWEEN 1 AND 255 "
            "AND relative_name=btrim(relative_name) "
            "AND position(chr(92) in relative_name) = 0 "
            "AND relative_name !~ '(^|/)\\.\\.(/|$)'",
            name="ck_plg_exec_result_files__relative_name"),
        CheckConstraint("char_length(media_type) BETWEEN 1 AND 255",
                        name="ck_plg_exec_result_files__mime"),
        CheckConstraint("octet_length(sha256) = 32",
                        name="ck_plg_exec_result_files__sha256"),
        CheckConstraint("size_bytes >= 0", name="ck_plg_exec_result_files__size"),
        CheckConstraint("isfinite(created_at)",
                        name="ck_plg_exec_result_files__created_at"),
        Index("ix_plg_exec_result_files__execution",
              "plugin_execution_id", "project_id", "created_at"),
        {"schema": "plm"},
    )

    result_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PROJECT'"))
    relative_name: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))


class PluginExecutionStateEventRow(Base):
    """Append-only sanitized PluginExecution lifecycle history."""

    __tablename__ = "plg_execution_state_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plugin_execution_id", "project_id"],
            ["plm.plg_executions.plugin_execution_id", "plm.plg_executions.project_id"],
            name="fk_plg_exec_state_events__execution_project", ondelete="NO ACTION"),
        CheckConstraint(
            "from_state IS NULL OR from_state IN "
            "('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_exec_state_events__from_state"),
        CheckConstraint(
            "to_state IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_plg_exec_state_events__to_state"),
        CheckConstraint(
            "reason_code IS NULL OR reason_code ~ '^[A-Z][A-Z0-9_]{0,63}$'",
            name="ck_plg_exec_state_events__reason"),
        CheckConstraint("isfinite(created_at)",
                        name="ck_plg_exec_state_events__created_at"),
        Index("ix_plg_exec_state_events__execution",
              "plugin_execution_id", "project_id", "created_at",
              "state_event_id"),
        {"schema": "plm"},
    )

    state_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    plugin_execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True, precision=6), nullable=False,
        server_default=text("statement_timestamp()"))
