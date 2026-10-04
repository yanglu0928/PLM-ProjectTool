"""CR-JOB-002 preserve first cancellation metadata without guessing old history."""
from alembic import context, op
import sqlalchemy as sa

revision="20260926_0039"
down_revision="20260926_0038"
branch_labels=None
depends_on=None

SHAPE="""(cancel_requested_by IS NULL AND cancel_reason IS NULL AND cancel_requested_at IS NULL)
 OR (cancel_requested_by IS NOT NULL AND cancel_reason IS NOT NULL AND cancel_requested_at IS NOT NULL
 AND cancel_requested_by<>'00000000-0000-0000-0000-000000000000'::uuid
 AND char_length(cancel_reason) BETWEEN 1 AND 1024 AND cancel_reason=btrim(cancel_reason)
 AND isfinite(cancel_requested_at) AND cancel_requested_at>=created_at
 AND state IN ('CANCEL_REQUESTED','CANCELLED'))"""


def upgrade():
    op.execute("""ALTER TABLE plm.job_jobs ADD COLUMN cancel_requested_by uuid,
        ADD COLUMN cancel_reason text, ADD COLUMN cancel_requested_at timestamptz(6)""")
    op.create_foreign_key("fk_job_jobs__cancel_user","job_jobs","auth_users",["cancel_requested_by"],["user_id"],source_schema="plm",referent_schema="plm")
    op.create_check_constraint("ck_job_jobs__cancel_shape","job_jobs",SHAPE,schema="plm")
    op.execute("""
        CREATE FUNCTION plm.guard_job_cancel_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='TRUNCATE' THEN
                IF EXISTS(SELECT 1 FROM plm.job_jobs WHERE cancel_requested_by IS NOT NULL) THEN
                    RAISE EXCEPTION 'Job cancellation history cannot be truncated';
                END IF;
                RETURN NULL;
            ELSIF TG_OP='DELETE' THEN
                IF OLD.cancel_requested_by IS NOT NULL THEN RAISE EXCEPTION 'Job cancellation history cannot be deleted'; END IF;
                RETURN OLD;
            ELSIF TG_OP='UPDATE' THEN
                IF OLD.cancel_requested_by IS NOT NULL THEN
                    IF (NEW.cancel_requested_by,NEW.cancel_reason,NEW.cancel_requested_at)
                         IS DISTINCT FROM (OLD.cancel_requested_by,OLD.cancel_reason,OLD.cancel_requested_at)
                        OR (NEW.job_id,NEW.owner_module,NEW.job_type,NEW.scope,NEW.project_id,
                            NEW.actor_ref,NEW.trace_id,NEW.payload_refs,NEW.idempotency_key)
                           IS DISTINCT FROM (OLD.job_id,OLD.owner_module,OLD.job_type,OLD.scope,OLD.project_id,
                            OLD.actor_ref,OLD.trace_id,OLD.payload_refs,OLD.idempotency_key)
                        OR NEW.state NOT IN ('CANCEL_REQUESTED','CANCELLED')
                        OR (OLD.state='CANCELLED' AND (NEW.state<>'CANCELLED'
                            OR NEW.completed_at IS DISTINCT FROM OLD.completed_at)) THEN
                        RAISE EXCEPTION 'Job cancellation history is immutable';
                    END IF;
                ELSIF NEW.cancel_requested_by IS NOT NULL AND
                    OLD.state NOT IN ('PENDING','RETRY_WAIT','RUNNING') THEN
                    RAISE EXCEPTION 'Job cancellation history cannot be backfilled';
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER trg_job_jobs_cancel_history BEFORE UPDATE OR DELETE ON plm.job_jobs
            FOR EACH ROW EXECUTE FUNCTION plm.guard_job_cancel_history();
        CREATE TRIGGER trg_job_jobs_cancel_no_truncate BEFORE TRUNCATE ON plm.job_jobs
            FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_job_cancel_history();
    """)


def downgrade():
    if context.is_offline_mode():raise RuntimeError("offline Job cancellation downgrade disabled")
    op.execute("LOCK TABLE plm.job_jobs IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.job_jobs WHERE cancel_requested_by IS NOT NULL OR cancel_reason IS NOT NULL OR cancel_requested_at IS NOT NULL)")):
        raise RuntimeError("Job cancellation history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_job_jobs_cancel_history ON plm.job_jobs; DROP TRIGGER trg_job_jobs_cancel_no_truncate ON plm.job_jobs; DROP FUNCTION plm.guard_job_cancel_history()")
    op.drop_constraint("ck_job_jobs__cancel_shape","job_jobs",schema="plm",type_="check")
    op.drop_constraint("fk_job_jobs__cancel_user","job_jobs",schema="plm",type_="foreignkey")
    for column in ("cancel_requested_at","cancel_reason","cancel_requested_by"):
        op.drop_column("job_jobs",column,schema="plm")
