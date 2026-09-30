"""CR-PAR-002: immutable Parser Job cancellation response version."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260930_0050"
down_revision = "20260927_0049"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_parse_cancel_versions",
        sa.Column("audit_event_id", UUID(as_uuid=True), nullable=False),
        sa.Column("lock_version", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("audit_event_id", name="pk_job_parse_cancel_versions"),
        sa.ForeignKeyConstraint(["audit_event_id"], ["plm.aud_events.audit_event_id"],
                                name="fk_job_parse_cancel_versions__audit"),
        sa.CheckConstraint(
            "audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid AND lock_version>=0",
            name="ck_job_parse_cancel_versions__shape",
        ),
        schema="plm",
    )
    op.execute("""
    CREATE FUNCTION plm.validate_parse_cancel_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM plm.aud_events e
        JOIN plm.job_jobs j ON j.job_id=e.target_object_id
        WHERE e.audit_event_id=NEW.audit_event_id
          AND e.actor_type='USER' AND e.actor_id IS NOT NULL
          AND e.original_actor_id IS NULL AND e.actor_hint_digest IS NULL
          AND e.outcome='SUCCESS' AND e.event_scope='PROJECT'
          AND e.target_project_id=j.project_id
          AND e.target_owner_module='jobs' AND e.target_object_type='JOB-01'
          AND e.target_version_id IS NULL AND e.reason_code='USER_REQUESTED'
          AND j.owner_module='document' AND j.job_type='DOCUMENT_PARSE'
          AND j.scope='PROJECT' AND j.project_id IS NOT NULL
          AND e.occurred_at>=j.created_at
          AND ((e.action='DOCUMENT_PARSE_CANCEL_REQUESTED'
            AND ((e.before_state IN ('PENDING','RETRY_WAIT') AND e.after_state='CANCELLED')
              OR (e.before_state='RUNNING' AND e.after_state='CANCEL_REQUESTED')))
            OR (e.action='DOCUMENT_PARSE_CANCEL_CHECKED'
              AND e.before_state=e.after_state
              AND e.after_state IN ('CANCEL_REQUESTED','CANCELLED','SUCCEEDED','FAILED')))
      ) THEN RAISE EXCEPTION 'Invalid Parser cancellation response source'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION plm.reject_parse_cancel_version_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Parser cancellation response versions are immutable'; END $$;
    CREATE TRIGGER trg_job_parse_cancel_version_source BEFORE INSERT ON plm.job_parse_cancel_versions
      FOR EACH ROW EXECUTE FUNCTION plm.validate_parse_cancel_version();
    CREATE TRIGGER trg_job_parse_cancel_version_immutable BEFORE UPDATE OR DELETE ON plm.job_parse_cancel_versions
      FOR EACH ROW EXECUTE FUNCTION plm.reject_parse_cancel_version_change();
    CREATE TRIGGER trg_job_parse_cancel_version_truncate BEFORE TRUNCATE ON plm.job_parse_cancel_versions
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_parse_cancel_version_change();
    """)


def downgrade():
    op.execute("""LOCK TABLE plm.job_parse_cancel_versions IN ACCESS EXCLUSIVE MODE;
    DO $$ BEGIN IF EXISTS(SELECT 1 FROM plm.job_parse_cancel_versions)
      THEN RAISE EXCEPTION 'Cannot discard Parser cancellation response versions'; END IF; END $$;""")
    op.drop_table("job_parse_cancel_versions", schema="plm")
    op.execute("DROP FUNCTION plm.validate_parse_cancel_version()")
    op.execute("DROP FUNCTION plm.reject_parse_cancel_version_change()")
