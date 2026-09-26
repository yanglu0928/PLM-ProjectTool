"""CR-AUD-001 preserve immutable first Job/Event/request Audit refs."""
from alembic import context,op
import sqlalchemy as sa

revision="20260926_0038"
down_revision="20260926_0037"
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
        CREATE TABLE plm.aud_export_acceptances (
            export_id uuid CONSTRAINT pk_aud_export_acceptances PRIMARY KEY,
            job_id uuid NOT NULL, event_id uuid NOT NULL, request_audit_event_id uuid NOT NULL,
            accepted_at timestamptz(6) NOT NULL DEFAULT statement_timestamp(),
            CONSTRAINT fk_aud_export_acceptances__export_id__aud_exports FOREIGN KEY(export_id) REFERENCES plm.aud_exports(export_id),
            CONSTRAINT fk_aud_export_acceptances__audit_event__aud_events FOREIGN KEY(request_audit_event_id) REFERENCES plm.aud_events(audit_event_id),
            CONSTRAINT uq_aud_export_acceptances__job_id UNIQUE(job_id),
            CONSTRAINT uq_aud_export_acceptances__event_id UNIQUE(event_id),
            CONSTRAINT uq_aud_export_acceptances__request_audit_event_id UNIQUE(request_audit_event_id),
            CONSTRAINT ck_aud_export_acceptances__shape CHECK(isfinite(accepted_at)
                AND export_id<>'00000000-0000-0000-0000-000000000000'::uuid
                AND job_id<>'00000000-0000-0000-0000-000000000000'::uuid
                AND event_id<>'00000000-0000-0000-0000-000000000000'::uuid
                AND request_audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid)
        );
        CREATE FUNCTION plm.guard_audit_export_acceptance() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE r plm.aud_exports%ROWTYPE;
        BEGIN
            SELECT * INTO STRICT r FROM plm.aud_exports WHERE export_id=NEW.export_id FOR UPDATE;
            IF NEW.accepted_at<r.requested_at OR NOT EXISTS(
                SELECT 1 FROM plm.aud_events e WHERE e.audit_event_id=NEW.request_audit_event_id
                AND e.trace_id=r.trace_id AND e.event_scope=r.scope
                AND e.target_project_id IS NOT DISTINCT FROM r.project_id
                AND e.actor_type='USER' AND e.actor_id=r.actor_id
                AND e.action='AUDIT_EXPORT_REQUESTED' AND e.outcome='SUCCESS'
                AND e.target_owner_module='jobs' AND e.target_object_type='JOB-01'
                AND e.target_object_id=NEW.job_id AND e.target_version_id IS NULL
                AND e.reason_code=r.purpose AND e.before_state IS NULL AND e.after_state='PENDING'
                AND e.occurred_at>=r.requested_at AND e.occurred_at<=NEW.accepted_at) THEN
                RAISE EXCEPTION 'Audit export acceptance binding mismatch';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER trg_aud_export_acceptances_insert BEFORE INSERT ON plm.aud_export_acceptances
            FOR EACH ROW EXECUTE FUNCTION plm.guard_audit_export_acceptance();
        CREATE TRIGGER trg_aud_export_acceptances_immutable BEFORE UPDATE OR DELETE ON plm.aud_export_acceptances
            FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_export_mutation();
        CREATE TRIGGER trg_aud_export_acceptances_no_truncate BEFORE TRUNCATE ON plm.aud_export_acceptances
            FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_export_mutation();
    """)


def downgrade():
    if context.is_offline_mode():raise RuntimeError("offline Audit acceptance downgrade disabled")
    op.execute("LOCK TABLE plm.aud_export_acceptances IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.aud_export_acceptances)")):
        raise RuntimeError("Audit acceptance history exists; downgrade refused")
    op.drop_table("aud_export_acceptances",schema="plm")
    op.execute("DROP FUNCTION plm.guard_audit_export_acceptance()")
