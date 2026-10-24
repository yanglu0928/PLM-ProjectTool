"""PLT-02 encrypted SecretRecord and controlled SecretVersion lifecycle."""

from __future__ import annotations

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260924_0011"
down_revision = "20260924_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plt_secret_records",
        sa.Column("secret_record_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("secret_state", sa.Text(), nullable=False, server_default=sa.text("'DISABLED'")),
        sa.Column("allowed_consumer", sa.Text(), nullable=False),
        sa.Column("current_version_ref", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_plt_secret_records__created_by__auth_users", ondelete="NO ACTION"),
        sa.CheckConstraint("purpose IN ('DATABASE_PASSWORD','AI_PROVIDER_KEY','RERANKER_KEY','INTEGRATION_CREDENTIAL')", name="ck_plt_secret_records__purpose"),
        sa.CheckConstraint("secret_state IN ('ACTIVE','DISABLED','RETIRED')", name="ck_plt_secret_records__state"),
        sa.CheckConstraint("allowed_consumer IN ('DATABASE_ADAPTER','AI_PROVIDER_ADAPTER','RERANKER_ADAPTER','INTEGRATION_ADAPTER')", name="ck_plt_secret_records__consumer"),
        sa.CheckConstraint("(purpose = 'DATABASE_PASSWORD' AND allowed_consumer = 'DATABASE_ADAPTER') OR (purpose = 'AI_PROVIDER_KEY' AND allowed_consumer = 'AI_PROVIDER_ADAPTER') OR (purpose = 'RERANKER_KEY' AND allowed_consumer = 'RERANKER_ADAPTER') OR (purpose = 'INTEGRATION_CREDENTIAL' AND allowed_consumer = 'INTEGRATION_ADAPTER')", name="ck_plt_secret_records__purpose_consumer"),
        sa.CheckConstraint("lock_version >= 0", name="ck_plt_secret_records__lock_version"),
        sa.CheckConstraint("secret_state <> 'ACTIVE' OR current_version_ref IS NOT NULL", name="ck_plt_secret_records__active_ref"),
        schema="plm",
    )
    op.create_table(
        "plt_secret_versions",
        sa.Column("secret_version_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("secret_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("key_provider_ref", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("activated_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("retired_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.ForeignKeyConstraint(["secret_record_id"], ["plm.plt_secret_records.secret_record_id"], name="fk_plt_secret_versions__secret_record_id__plt_secret_records", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"], name="fk_plt_secret_versions__created_by__auth_users", ondelete="NO ACTION"),
        sa.UniqueConstraint("secret_record_id", "version_no", name="uq_plt_secret_versions__record_no"),
        sa.UniqueConstraint("secret_version_id", "secret_record_id", name="uq_plt_secret_versions__identity_parent"),
        sa.CheckConstraint("version_no > 0", name="ck_plt_secret_versions__version_no"),
        sa.CheckConstraint("octet_length(encrypted_payload) BETWEEN 1 AND 65536", name="ck_plt_secret_versions__cipher_size"),
        sa.CheckConstraint("jsonb_typeof(encryption_metadata) = 'object'", name="ck_plt_secret_versions__metadata"),
        sa.CheckConstraint("char_length(key_provider_ref) BETWEEN 1 AND 128 AND key_provider_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'", name="ck_plt_secret_versions__key_ref"),
        sa.CheckConstraint("retired_at IS NULL OR (activated_at IS NOT NULL AND retired_at >= activated_at)", name="ck_plt_secret_versions__lifecycle"),
        schema="plm",
    )
    op.create_index("uq_plt_secret_versions__record_active", "plt_secret_versions", ["secret_record_id"], unique=True,
                    schema="plm", postgresql_where=sa.text("activated_at IS NOT NULL AND retired_at IS NULL"))
    op.create_foreign_key("fk_plt_secret_records__current_version", "plt_secret_records", "plt_secret_versions",
                          ["current_version_ref", "secret_record_id"], ["secret_version_id", "secret_record_id"],
                          source_schema="plm", referent_schema="plm", ondelete="NO ACTION")
    op.execute("""
        CREATE FUNCTION plm.guard_plt_secret_record_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
                RAISE EXCEPTION 'secret record history cannot be deleted';
            END IF;
            IF NEW.secret_record_id IS DISTINCT FROM OLD.secret_record_id
               OR NEW.purpose IS DISTINCT FROM OLD.purpose
               OR NEW.allowed_consumer IS DISTINCT FROM OLD.allowed_consumer
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.lock_version <> OLD.lock_version + 1
               OR NEW.updated_at < OLD.updated_at
               OR OLD.secret_state = 'RETIRED'
               OR (OLD.secret_state = 'ACTIVE' AND NEW.secret_state NOT IN ('ACTIVE','DISABLED','RETIRED'))
               OR (OLD.secret_state = 'DISABLED' AND NEW.secret_state NOT IN ('DISABLED','ACTIVE','RETIRED'))
            THEN
                RAISE EXCEPTION 'invalid secret record transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("CREATE TRIGGER trg_plt_secret_records_guard BEFORE UPDATE OR DELETE ON plm.plt_secret_records FOR EACH ROW EXECUTE FUNCTION plm.guard_plt_secret_record_change()")
    op.execute("CREATE TRIGGER trg_plt_secret_records_truncate_guard BEFORE TRUNCATE ON plm.plt_secret_records FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_plt_secret_record_change()")
    op.execute("""
        CREATE FUNCTION plm.guard_plt_secret_version_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
                RAISE EXCEPTION 'secret version history cannot be deleted';
            END IF;
            IF NEW.secret_version_id IS DISTINCT FROM OLD.secret_version_id
               OR NEW.secret_record_id IS DISTINCT FROM OLD.secret_record_id
               OR NEW.version_no IS DISTINCT FROM OLD.version_no
               OR NEW.encrypted_payload IS DISTINCT FROM OLD.encrypted_payload
               OR NEW.encryption_metadata IS DISTINCT FROM OLD.encryption_metadata
               OR NEW.key_provider_ref IS DISTINCT FROM OLD.key_provider_ref
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR (OLD.activated_at IS NULL AND (NEW.retired_at IS NOT NULL OR NEW.activated_at IS NULL))
               OR (OLD.activated_at IS NOT NULL AND NEW.activated_at IS DISTINCT FROM OLD.activated_at)
               OR (OLD.retired_at IS NOT NULL)
               OR (OLD.activated_at IS NOT NULL AND NEW.retired_at IS NULL)
            THEN
                RAISE EXCEPTION 'invalid secret version transition';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("CREATE TRIGGER trg_plt_secret_versions_guard BEFORE UPDATE OR DELETE ON plm.plt_secret_versions FOR EACH ROW EXECUTE FUNCTION plm.guard_plt_secret_version_change()")
    op.execute("CREATE TRIGGER trg_plt_secret_versions_truncate_guard BEFORE TRUNCATE ON plm.plt_secret_versions FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_plt_secret_version_change()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled: Secret history must be checked")
    bind = op.get_bind()
    for table in ("plt_secret_versions", "plt_secret_records"):
        if bind.scalar(sa.text(f"SELECT count(*) FROM plm.{table}")):
            raise RuntimeError("Secret history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_plt_secret_versions_truncate_guard ON plm.plt_secret_versions")
    op.execute("DROP TRIGGER trg_plt_secret_versions_guard ON plm.plt_secret_versions")
    op.execute("DROP FUNCTION plm.guard_plt_secret_version_change()")
    op.execute("DROP TRIGGER trg_plt_secret_records_truncate_guard ON plm.plt_secret_records")
    op.execute("DROP TRIGGER trg_plt_secret_records_guard ON plm.plt_secret_records")
    op.execute("DROP FUNCTION plm.guard_plt_secret_record_change()")
    op.drop_constraint("fk_plt_secret_records__current_version", "plt_secret_records", schema="plm", type_="foreignkey")
    op.drop_index("uq_plt_secret_versions__record_active", table_name="plt_secret_versions", schema="plm")
    op.drop_table("plt_secret_versions", schema="plm")
    op.drop_table("plt_secret_records", schema="plm")
