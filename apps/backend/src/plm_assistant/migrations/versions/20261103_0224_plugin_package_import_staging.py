"""Add immutable detached signature metadata for asynchronous Plugin import."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261103_0224"
down_revision = "20261103_0223"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plg_package_import_stagings",
        sa.Column("package_upload_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("package_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("package_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("detached_signature", sa.LargeBinary(), nullable=False),
        sa.Column("signer_key_ref", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True, precision=6),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.CheckConstraint(
            "package_upload_id <> '00000000-0000-0000-0000-000000000000'::uuid",
            name="ck_plg_package_import_stagings__id",
        ),
        sa.CheckConstraint(
            "octet_length(package_sha256) = 32",
            name="ck_plg_package_import_stagings__hash",
        ),
        sa.CheckConstraint(
            "package_size_bytes BETWEEN 1 AND 268435456",
            name="ck_plg_package_import_stagings__size",
        ),
        sa.CheckConstraint(
            "octet_length(detached_signature) = 64",
            name="ck_plg_package_import_stagings__signature",
        ),
        sa.CheckConstraint(
            "char_length(signer_key_ref) BETWEEN 1 AND 512 "
            "AND signer_key_ref = btrim(signer_key_ref)",
            name="ck_plg_package_import_stagings__signer_ref",
        ),
        sa.CheckConstraint(
            "isfinite(created_at)",
            name="ck_plg_package_import_stagings__created_at",
        ),
        schema="plm",
    )
    op.create_index(
        "ix_plg_package_import_stagings__created",
        "plg_package_import_stagings",
        ["created_at", "package_upload_id"],
        schema="plm",
    )
    op.execute("""
CREATE OR REPLACE FUNCTION plm.reject_plugin_package_import_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plugin package import staging history is immutable';
END; $$;
""")
    op.execute("""
CREATE OR REPLACE FUNCTION plm.reject_plugin_package_import_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Plugin package import staging history cannot be truncated';
END; $$;
""")
    op.execute("""
CREATE TRIGGER trg_plg_package_import_stagings__immutable
BEFORE UPDATE OR DELETE ON plm.plg_package_import_stagings
FOR EACH ROW EXECUTE FUNCTION plm.reject_plugin_package_import_mutation();
""")
    op.execute("""
CREATE TRIGGER trg_plg_package_import_stagings__no_truncate
BEFORE TRUNCATE ON plm.plg_package_import_stagings
FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_plugin_package_import_truncate();
""")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Plugin import staging downgrade is disabled")
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM plm.plg_package_import_stagings)"
    )).scalar_one():
        raise RuntimeError("Plugin package import staging history prevents downgrade")
    op.execute(
        "DROP TRIGGER trg_plg_package_import_stagings__immutable "
        "ON plm.plg_package_import_stagings"
    )
    op.execute(
        "DROP TRIGGER trg_plg_package_import_stagings__no_truncate "
        "ON plm.plg_package_import_stagings"
    )
    op.drop_index(
        "ix_plg_package_import_stagings__created",
        table_name="plg_package_import_stagings",
        schema="plm",
    )
    op.drop_table("plg_package_import_stagings", schema="plm")
    op.execute("DROP FUNCTION plm.reject_plugin_package_import_mutation()")
    op.execute("DROP FUNCTION plm.reject_plugin_package_import_truncate()")
