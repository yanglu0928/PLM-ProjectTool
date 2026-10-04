"""LIC-01 signed LicenseInstallation history and immutable documents."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0008"
down_revision = "20260924_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lic_installations",
        sa.Column("license_installation_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("public_key_ref", sa.Text(), nullable=False),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("imported_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("installation_state", sa.Text(), nullable=False, server_default=sa.text("'IMPORTED'")),
        sa.Column("validation_result_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("import_trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["imported_by"], ["plm.auth_users.user_id"], name="fk_lic_installations__importer", ondelete="NO ACTION"),
        sa.CheckConstraint("installation_state IN ('IMPORTED','ACTIVE','SUPERSEDED','REJECTED')", name="ck_lic_installations__state"),
        sa.CheckConstraint("installation_state = 'IMPORTED' OR validation_result_ref IS NOT NULL", name="ck_lic_installations__validated_state"),
        sa.CheckConstraint("char_length(public_key_ref) BETWEEN 1 AND 128 AND public_key_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'", name="ck_lic_installations__public_key_ref"),
        sa.CheckConstraint("lock_version >= 0", name="ck_lic_installations__lock_version"),
        schema="plm",
    )
    op.create_index("ix_lic_installations__imported_by", "lic_installations", ["imported_by"], schema="plm")
    op.create_index("ix_lic_installations__imported", "lic_installations", ["imported_at", "license_installation_id"], schema="plm")
    op.create_index("uq_lic_installations__one_active", "lic_installations", ["installation_state"], unique=True, postgresql_where=sa.text("installation_state = 'ACTIVE'"), schema="plm")
    op.create_table(
        "lic_installation_documents",
        sa.Column("license_document_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("license_installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signed_document", sa.LargeBinary(), nullable=False),
        sa.Column("document_sha256", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["license_installation_id"], ["plm.lic_installations.license_installation_id"], name="fk_lic_installation_documents__installation", ondelete="NO ACTION"),
        sa.UniqueConstraint("license_installation_id", name="uq_lic_installation_documents__installation"),
        sa.CheckConstraint("octet_length(signed_document) BETWEEN 1 AND 65536", name="ck_lic_installation_documents__size"),
        sa.CheckConstraint("octet_length(document_sha256) = 32", name="ck_lic_installation_documents__sha256"),
        schema="plm",
    )
    op.execute("""
        CREATE FUNCTION plm.guard_lic_installation_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'license installation history is immutable';
            ELSE
                IF NEW.public_key_ref IS DISTINCT FROM OLD.public_key_ref
                   OR NEW.imported_by IS DISTINCT FROM OLD.imported_by
                   OR NEW.imported_at IS DISTINCT FROM OLD.imported_at
                   OR NEW.import_trace_id IS DISTINCT FROM OLD.import_trace_id
                   OR NEW.lock_version <> OLD.lock_version + 1
                   OR OLD.installation_state IN ('REJECTED','SUPERSEDED')
                   OR (OLD.installation_state = 'IMPORTED' AND NEW.installation_state NOT IN ('IMPORTED','ACTIVE','REJECTED'))
                   OR (OLD.installation_state = 'ACTIVE' AND NEW.installation_state NOT IN ('ACTIVE','SUPERSEDED'))
                   OR (NEW.installation_state IN ('ACTIVE','REJECTED','SUPERSEDED') AND NEW.validation_result_ref IS NULL)
                THEN
                    RAISE EXCEPTION 'invalid license installation transition';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_installations_guard
        BEFORE UPDATE OR DELETE ON plm.lic_installations
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_installation_change()
    """)
    op.execute("""
        CREATE FUNCTION plm.guard_lic_document_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'signed license document is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_lic_documents_guard
        BEFORE UPDATE OR DELETE ON plm.lic_installation_documents
        FOR EACH ROW EXECUTE FUNCTION plm.guard_lic_document_change()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: license history must be checked")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM plm.lic_installations")) or bind.scalar(sa.text("SELECT count(*) FROM plm.lic_installation_documents")):
        raise RuntimeError("license history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_lic_documents_guard ON plm.lic_installation_documents")
    op.execute("DROP FUNCTION plm.guard_lic_document_change()")
    op.execute("DROP TRIGGER trg_lic_installations_guard ON plm.lic_installations")
    op.execute("DROP FUNCTION plm.guard_lic_installation_change()")
    op.drop_table("lic_installation_documents", schema="plm")
    op.drop_index("uq_lic_installations__one_active", table_name="lic_installations", schema="plm")
    op.drop_index("ix_lic_installations__imported", table_name="lic_installations", schema="plm")
    op.drop_index("ix_lic_installations__imported_by", table_name="lic_installations", schema="plm")
    op.drop_table("lic_installations", schema="plm")
