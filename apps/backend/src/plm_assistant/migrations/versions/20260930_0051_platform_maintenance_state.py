"""CR-PLT-004: durable singleton maintenance state, not yet an admission fence."""

from alembic import op
import sqlalchemy as sa

revision = "20260930_0051"
down_revision = "20260930_0050"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plt_maintenance_state",
        sa.Column("state_id", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("state_id", name="pk_plt_maintenance_state"),
        sa.CheckConstraint("state_id=1 AND state IN ('RUNNING','MAINTENANCE') "
                           "AND lock_version>=0",
                           name="ck_plt_maintenance_state__shape"),
        schema="plm",
    )
    op.execute("""
    CREATE FUNCTION plm.guard_maintenance_state_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Maintenance state cannot be deleted'; END IF;
      IF NEW.state_id<>OLD.state_id OR NEW.state=OLD.state
         OR NEW.lock_version<>OLD.lock_version+1 THEN
        RAISE EXCEPTION 'Invalid maintenance state transition';
      END IF;
      NEW.changed_at:=clock_timestamp();
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_maintenance_state_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Maintenance state cannot be truncated'; END $$;
    CREATE TRIGGER trg_plt_maintenance_state_change
      BEFORE UPDATE OR DELETE ON plm.plt_maintenance_state
      FOR EACH ROW EXECUTE FUNCTION plm.guard_maintenance_state_change();
    CREATE TRIGGER trg_plt_maintenance_state_truncate
      BEFORE TRUNCATE ON plm.plt_maintenance_state
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_maintenance_state_truncate();
    INSERT INTO plm.plt_maintenance_state(state_id,state,lock_version,changed_at)
      VALUES (1,'RUNNING',0,clock_timestamp());
    """)


def downgrade():
    op.execute("""
    LOCK TABLE plm.plt_maintenance_state IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN
      IF (SELECT count(*) FROM plm.plt_maintenance_state)<>1
         OR NOT EXISTS (SELECT 1 FROM plm.plt_maintenance_state
                        WHERE state_id=1 AND state='RUNNING' AND lock_version=0) THEN
        RAISE EXCEPTION 'Cannot discard maintenance state history';
      END IF;
    END $$;
    """)
    op.drop_table("plt_maintenance_state", schema="plm")
    op.execute("DROP FUNCTION plm.guard_maintenance_state_change()")
    op.execute("DROP FUNCTION plm.reject_maintenance_state_truncate()")
