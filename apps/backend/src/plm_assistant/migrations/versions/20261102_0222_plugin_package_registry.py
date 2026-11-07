"""Add closed PLG-01 signed package registry metadata."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261102_0222"
down_revision = "20261102_0221"
branch_labels = None
depends_on = None


_GUARDS = r"""
CREATE OR REPLACE FUNCTION plm.reject_plugin_package_write()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PluginPackage Owner is not installed';
END; $$;

CREATE OR REPLACE FUNCTION plm.reject_plugin_package_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'PluginPackage history cannot be truncated';
END; $$;
"""


def upgrade() -> None:
    ident = postgresql.UUID(as_uuid=True)
    timestamp = postgresql.TIMESTAMP(timezone=True, precision=6)
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "plg_packages",
        sa.Column("plugin_package_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plugin_id_normalized", sa.Text(), nullable=False),
        sa.Column("plugin_version", sa.Text(), nullable=False),
        sa.Column("package_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("manifest_snapshot", jsonb, nullable=False),
        sa.Column("signature", sa.LargeBinary(), nullable=False),
        sa.Column("signer_key_ref", sa.Text(), nullable=False),
        sa.Column("compatibility_policy_ref", sa.Text(), nullable=False),
        sa.Column("package_state", sa.Text(), nullable=False,
                  server_default=sa.text("'IMPORTED'")),
        sa.Column("verified_at", timestamp),
        sa.Column("verification_summary", sa.Text()),
        sa.Column("created_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False,
                  server_default=sa.text("0")),
        sa.UniqueConstraint("plugin_package_id", "plugin_id_normalized",
                            name="uq_plg_packages__id_plugin"),
        sa.UniqueConstraint("plugin_id_normalized", "plugin_version",
                            name="uq_plg_packages__plugin_version"),
        sa.CheckConstraint(
            "plugin_id_normalized = lower(plugin_id_normalized) "
            "AND plugin_id_normalized ~ '^[a-z0-9][a-z0-9._-]{1,127}$'",
            name="ck_plg_packages__plugin_id"),
        sa.CheckConstraint(
            "char_length(plugin_version) BETWEEN 1 AND 64 "
            "AND plugin_version = btrim(plugin_version)",
            name="ck_plg_packages__version"),
        sa.CheckConstraint("octet_length(package_sha256) = 32",
                           name="ck_plg_packages__hash"),
        sa.CheckConstraint("octet_length(signature) BETWEEN 1 AND 4096",
                           name="ck_plg_packages__signature"),
        sa.CheckConstraint(
            "jsonb_typeof(manifest_snapshot) = 'object' "
            "AND manifest_snapshot ? 'schema_version'",
            name="ck_plg_packages__manifest"),
        sa.CheckConstraint(
            "package_state IN ('IMPORTED','VERIFIED','REJECTED','REVOKED')",
            name="ck_plg_packages__state"),
        sa.CheckConstraint(
            "(package_state = 'IMPORTED' AND verified_at IS NULL) "
            "OR (package_state IN ('VERIFIED','REJECTED','REVOKED') "
            "AND verified_at IS NOT NULL)",
            name="ck_plg_packages__verification_time"),
        sa.CheckConstraint(
            "lock_version >= 0 AND isfinite(created_at) "
            "AND (verified_at IS NULL OR isfinite(verified_at))",
            name="ck_plg_packages__time_lock"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_packages__state_created", "plg_packages",
        ["package_state", "created_at", "plugin_package_id"], schema="plm")

    op.create_table(
        "plg_manifest_operations",
        sa.Column("plugin_package_id", ident, nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("output_types", jsonb, nullable=False),
        sa.Column("plugin_api_version", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("plugin_package_id", "operation_id",
                                name="pk_plg_manifest_operations"),
        sa.ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_manifest_operations__package", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "char_length(operation_id) BETWEEN 1 AND 255 "
            "AND operation_id = btrim(operation_id)",
            name="ck_plg_manifest_operations__operation"),
        sa.CheckConstraint(
            "jsonb_typeof(output_types) = 'array' "
            "AND jsonb_array_length(output_types) > 0",
            name="ck_plg_manifest_operations__output_types"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_manifest_operations__operation", "plg_manifest_operations",
        ["operation_id", "plugin_package_id"], schema="plm")

    op.create_table(
        "plg_manifest_dependencies",
        sa.Column("dependency_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plugin_package_id", ident, nullable=False),
        sa.Column("dependency_name", sa.Text(), nullable=False),
        sa.Column("version_spec", sa.Text(), nullable=False),
        sa.Column("dependency_kind", sa.Text(), nullable=False),
        sa.UniqueConstraint("plugin_package_id", "dependency_name",
                            name="uq_plg_manifest_dependencies__package_name"),
        sa.ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_manifest_dependencies__package", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "char_length(dependency_name) BETWEEN 1 AND 255 "
            "AND dependency_name = btrim(dependency_name)",
            name="ck_plg_manifest_dependencies__name"),
        sa.CheckConstraint(
            "char_length(version_spec) BETWEEN 1 AND 255 "
            "AND version_spec = btrim(version_spec)",
            name="ck_plg_manifest_dependencies__version_spec"),
        sa.CheckConstraint(
            "dependency_kind IN ('PYTHON','OS','SYSTEM')",
            name="ck_plg_manifest_dependencies__kind"),
        schema="plm",
    )

    op.create_table(
        "plg_package_verifications",
        sa.Column("verification_id", ident, primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("plugin_package_id", ident, nullable=False),
        sa.Column("verification_state", sa.Text(), nullable=False),
        sa.Column("check_code", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_fingerprint", sa.LargeBinary()),
        sa.Column("verified_at", timestamp, nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(
            ["plugin_package_id"], ["plm.plg_packages.plugin_package_id"],
            name="fk_plg_package_verifications__package", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "verification_state IN ('PASSED','FAILED','INCOMPATIBLE')",
            name="ck_plg_package_verifications__state"),
        sa.CheckConstraint(
            "char_length(check_code) BETWEEN 1 AND 128 "
            "AND check_code = btrim(check_code)",
            name="ck_plg_package_verifications__check_code"),
        sa.CheckConstraint(
            "char_length(summary) BETWEEN 1 AND 2000 "
            "AND summary = btrim(summary)",
            name="ck_plg_package_verifications__summary"),
        sa.CheckConstraint(
            "evidence_fingerprint IS NULL OR octet_length(evidence_fingerprint) = 32",
            name="ck_plg_package_verifications__fingerprint"),
        sa.CheckConstraint("isfinite(verified_at)",
                           name="ck_plg_package_verifications__verified_at"),
        schema="plm",
    )
    op.create_index(
        "ix_plg_package_verifications__package_time",
        "plg_package_verifications",
        ["plugin_package_id", "verified_at", "verification_id"], schema="plm")

    op.execute(_GUARDS)
    for table in (
        "plg_packages",
        "plg_manifest_operations",
        "plg_manifest_dependencies",
        "plg_package_verifications",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}__owner_closed "
            f"BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} "
            "FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_package_write()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}__no_truncate "
            f"BEFORE TRUNCATE ON plm.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plugin_package_truncate()"
        )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline PluginPackage downgrade is disabled")
    bind = op.get_bind()
    for table in (
        "plg_package_verifications",
        "plg_manifest_dependencies",
        "plg_manifest_operations",
        "plg_packages",
    ):
        if bind.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM plm.{table})"
        )).scalar_one():
            raise RuntimeError("PluginPackage history prevents downgrade")
    for table in (
        "plg_packages",
        "plg_manifest_operations",
        "plg_manifest_dependencies",
        "plg_package_verifications",
    ):
        op.execute(f"DROP TRIGGER trg_{table}__owner_closed ON plm.{table}")
        op.execute(f"DROP TRIGGER trg_{table}__no_truncate ON plm.{table}")
    op.drop_index("ix_plg_package_verifications__package_time",
                  table_name="plg_package_verifications", schema="plm")
    op.drop_table("plg_package_verifications", schema="plm")
    op.drop_table("plg_manifest_dependencies", schema="plm")
    op.drop_index("ix_plg_manifest_operations__operation",
                  table_name="plg_manifest_operations", schema="plm")
    op.drop_table("plg_manifest_operations", schema="plm")
    op.drop_index("ix_plg_packages__state_created",
                  table_name="plg_packages", schema="plm")
    op.drop_table("plg_packages", schema="plm")
    op.execute("DROP FUNCTION plm.reject_plugin_package_write()")
    op.execute("DROP FUNCTION plm.reject_plugin_package_truncate()")
