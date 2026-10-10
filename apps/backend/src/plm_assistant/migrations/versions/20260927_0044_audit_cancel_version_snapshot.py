"""CR-JOB-004: append-only first cancellation response version."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision='20260927_0044'
down_revision='20260927_0043'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('aud_export_cancel_versions',
        sa.Column('audit_event_id',UUID(as_uuid=True),nullable=False),
        sa.Column('lock_version',sa.BigInteger(),nullable=False),
        sa.PrimaryKeyConstraint('audit_event_id',name='pk_aud_export_cancel_versions'),
        sa.ForeignKeyConstraint(['audit_event_id'],['plm.aud_events.audit_event_id'],name='fk_aud_export_cancel_versions__audit'),
        sa.CheckConstraint("audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid AND lock_version>=0",name='ck_aud_export_cancel_versions__shape'),schema='plm')
    op.execute("""
    CREATE FUNCTION plm.validate_audit_cancel_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM plm.aud_events e
        JOIN plm.aud_export_acceptances a ON a.job_id=e.target_object_id
        JOIN plm.aud_exports r ON r.export_id=a.export_id
        WHERE e.audit_event_id=NEW.audit_event_id
          AND e.actor_type='USER' AND e.actor_id IS NOT NULL
          AND e.original_actor_id IS NULL AND e.actor_hint_digest IS NULL
          AND e.outcome='SUCCESS' AND e.target_owner_module='jobs'
          AND e.target_object_type='JOB-01' AND e.target_version_id IS NULL
          AND e.reason_code='USER_REQUESTED'
          AND e.event_scope=r.scope AND e.target_project_id IS NOT DISTINCT FROM r.project_id
          AND e.occurred_at>=a.accepted_at
          AND ((e.action='AUDIT_EXPORT_CANCEL_REQUESTED'
            AND ((e.before_state IN ('PENDING','RETRY_WAIT') AND e.after_state='CANCELLED')
              OR (e.before_state='RUNNING' AND e.after_state='CANCEL_REQUESTED')))
            OR (e.action='AUDIT_EXPORT_CANCEL_CHECKED'
              AND e.before_state=e.after_state
              AND e.after_state IN ('CANCEL_REQUESTED','CANCELLED','SUCCEEDED','FAILED')))
      ) THEN RAISE EXCEPTION 'Invalid cancellation response source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_audit_cancel_version_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Cancellation response versions are immutable'; END $$;
    CREATE TRIGGER trg_aud_cancel_version_source BEFORE INSERT ON plm.aud_export_cancel_versions
      FOR EACH ROW EXECUTE FUNCTION plm.validate_audit_cancel_version();
    CREATE TRIGGER trg_aud_cancel_version_immutable BEFORE UPDATE OR DELETE ON plm.aud_export_cancel_versions
      FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_cancel_version_change();
    CREATE TRIGGER trg_aud_cancel_version_truncate BEFORE TRUNCATE ON plm.aud_export_cancel_versions
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_cancel_version_change();
    """)

def downgrade():
    op.execute("""LOCK TABLE plm.aud_export_cancel_versions IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.aud_export_cancel_versions)
      THEN RAISE EXCEPTION 'Cannot discard cancellation response versions'; END IF; END $$;""")
    op.drop_table('aud_export_cancel_versions',schema='plm')
    op.execute('DROP FUNCTION plm.validate_audit_cancel_version()')
    op.execute('DROP FUNCTION plm.reject_audit_cancel_version_change()')
