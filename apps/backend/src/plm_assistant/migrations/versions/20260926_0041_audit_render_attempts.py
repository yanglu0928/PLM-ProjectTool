"""CR-AUD-002 immutable physical rendering plan; not current Job authority."""
from alembic import context,op
import sqlalchemy as sa

revision="20260926_0041"
down_revision="20260926_0040"
branch_labels=None
depends_on=None

SHAPE="""render_attempt_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND export_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND job_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND file_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND fencing_token>0 AND attempt_no>0 AND member_count BETWEEN 0 AND 100000
 AND worker_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
 AND membership_hash ~ '^[0-9a-f]{64}$'
 AND membership_version='CAPTURE-MEMBERSHIP-V1' AND isfinite(created_at)"""


def upgrade():
    op.execute("""
    CREATE TABLE plm.aud_export_render_attempts (
      render_attempt_id uuid DEFAULT uuidv7() CONSTRAINT pk_aud_export_render_attempts PRIMARY KEY,
      export_id uuid NOT NULL, job_id uuid NOT NULL, fencing_token bigint NOT NULL, attempt_no integer NOT NULL,
      worker_ref text NOT NULL, file_id uuid NOT NULL, member_count bigint NOT NULL,
      membership_hash text NOT NULL, membership_version text NOT NULL,
      created_at timestamptz(6) NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT fk_aud_render_attempts__capture FOREIGN KEY(export_id) REFERENCES plm.aud_export_captures(export_id),
      CONSTRAINT fk_aud_render_attempts__acceptance FOREIGN KEY(export_id) REFERENCES plm.aud_export_acceptances(export_id),
      CONSTRAINT uq_aud_render_attempts__job_fence UNIQUE(job_id,fencing_token),
      CONSTRAINT uq_aud_render_attempts__file UNIQUE(file_id)
    )
    """)
    op.create_check_constraint("ck_aud_render_attempts__shape","aud_export_render_attempts",SHAPE,schema="plm")
    op.create_index("ix_aud_render_attempts__export_created","aud_export_render_attempts",["export_id","created_at"],schema="plm")
    op.execute("""
    CREATE FUNCTION plm.guard_audit_render_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r plm.aud_exports%ROWTYPE; c plm.aud_export_captures%ROWTYPE; a plm.aud_export_acceptances%ROWTYPE;
    BEGIN
      SELECT * INTO r FROM plm.aud_exports WHERE export_id=NEW.export_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Audit rendering root missing'; END IF;
      SELECT * INTO c FROM plm.aud_export_captures WHERE export_id=NEW.export_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'Audit rendering capture missing'; END IF;
      SELECT * INTO a FROM plm.aud_export_acceptances WHERE export_id=NEW.export_id;
      IF NOT FOUND THEN RAISE EXCEPTION 'Audit rendering acceptance missing'; END IF;
      IF NEW.job_id<>a.job_id
        OR (NEW.member_count,NEW.membership_hash,NEW.membership_version)
           IS DISTINCT FROM (c.member_count,c.membership_hash,c.membership_version)
        OR NEW.created_at<r.requested_at OR NEW.created_at<c.captured_at OR NEW.created_at<a.accepted_at THEN
          RAISE EXCEPTION 'Audit rendering source binding mismatch';
      END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER trg_aud_render_attempts_insert BEFORE INSERT ON plm.aud_export_render_attempts
      FOR EACH ROW EXECUTE FUNCTION plm.guard_audit_render_attempt();
    CREATE TRIGGER trg_aud_render_attempts_immutable BEFORE UPDATE OR DELETE ON plm.aud_export_render_attempts
      FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_export_mutation();
    CREATE TRIGGER trg_aud_render_attempts_no_truncate BEFORE TRUNCATE ON plm.aud_export_render_attempts
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_export_mutation();
    """)


def downgrade():
    if context.is_offline_mode():raise RuntimeError("offline Audit rendering downgrade disabled")
    op.execute("LOCK TABLE plm.aud_export_render_attempts IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.aud_export_render_attempts)")):
        raise RuntimeError("Audit rendering history exists; downgrade refused")
    op.drop_table("aud_export_render_attempts",schema="plm")
    op.execute("DROP FUNCTION plm.guard_audit_render_attempt()")
