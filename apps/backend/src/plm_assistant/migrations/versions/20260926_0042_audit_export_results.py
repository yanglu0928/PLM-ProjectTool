"""CR-AUD-002 own immutable result/source/manifest integrity; not runtime authority."""
from alembic import context,op
import sqlalchemy as sa

revision='20260926_0042'
down_revision='20260926_0041'
branch_labels=None
depends_on=None

SHAPE="""export_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND render_attempt_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND file_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND publish_audit_event_id<>'00000000-0000-0000-0000-000000000000'::uuid
 AND octet_length(file_sha256)=32 AND byte_count BETWEEN 0 AND 134217728
 AND mime_type='application/x-ndjson' AND manifest_version='AUDIT-EXPORT-MANIFEST-V1'
 AND octet_length(manifest_bytes) BETWEEN 1 AND 8192
 AND octet_length(manifest_sha256)=32 AND manifest_sha256=sha256(manifest_bytes)
 AND isfinite(published_at)"""


def upgrade():
    op.execute("""
    CREATE TABLE plm.aud_export_results (
      export_id uuid CONSTRAINT pk_aud_export_results PRIMARY KEY,
      render_attempt_id uuid NOT NULL, file_id uuid NOT NULL, file_sha256 bytea NOT NULL,
      byte_count bigint NOT NULL, mime_type text NOT NULL, manifest_version text NOT NULL,
      manifest_bytes bytea NOT NULL, manifest_sha256 bytea NOT NULL,
      publish_audit_event_id uuid NOT NULL, published_at timestamptz(6) NOT NULL DEFAULT statement_timestamp(),
      CONSTRAINT fk_aud_export_results__export FOREIGN KEY(export_id) REFERENCES plm.aud_exports(export_id),
      CONSTRAINT fk_aud_export_results__attempt FOREIGN KEY(render_attempt_id) REFERENCES plm.aud_export_render_attempts(render_attempt_id),
      CONSTRAINT fk_aud_export_results__audit FOREIGN KEY(publish_audit_event_id) REFERENCES plm.aud_events(audit_event_id),
      CONSTRAINT uq_aud_export_results__attempt UNIQUE(render_attempt_id),
      CONSTRAINT uq_aud_export_results__file UNIQUE(file_id),
      CONSTRAINT uq_aud_export_results__audit UNIQUE(publish_audit_event_id)
    )
    """)
    op.create_check_constraint('ck_aud_export_results__shape','aud_export_results',SHAPE,schema='plm')
    op.execute("""
    CREATE FUNCTION plm.guard_audit_export_result() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r plm.aud_exports%ROWTYPE; p plm.aud_export_render_attempts%ROWTYPE;
      c plm.aud_export_captures%ROWTYPE; a plm.aud_events%ROWTYPE;
      expected jsonb; canonical text;
    BEGIN
      SELECT * INTO r FROM plm.aud_exports WHERE export_id=NEW.export_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'Audit result root missing'; END IF;
      SELECT * INTO p FROM plm.aud_export_render_attempts WHERE render_attempt_id=NEW.render_attempt_id;
      IF NOT FOUND OR (p.export_id,p.file_id) IS DISTINCT FROM (NEW.export_id,NEW.file_id) THEN
        RAISE EXCEPTION 'Audit result plan binding mismatch'; END IF;
      SELECT * INTO c FROM plm.aud_export_captures WHERE export_id=r.export_id;
      IF NOT FOUND OR NEW.published_at<p.created_at OR NEW.published_at<c.captured_at THEN
        RAISE EXCEPTION 'Audit result capture/time missing'; END IF;
      SELECT * INTO a FROM plm.aud_events WHERE audit_event_id=NEW.publish_audit_event_id;
      IF NOT FOUND OR a.actor_id IS NULL OR a.actor_id='00000000-0000-0000-0000-000000000000'::uuid
        OR (a.actor_type,a.original_actor_id,a.trace_id,a.event_scope,a.target_project_id,
          a.action,a.outcome,a.target_owner_module,a.target_object_type,a.target_object_id,
          a.target_version_id,a.reason_code,a.before_state,a.after_state)
        IS DISTINCT FROM ('SYSTEM',r.actor_id,r.trace_id,r.scope,r.project_id,
          'AUDIT_EXPORT_PUBLISHED','SUCCESS','jobs','JOB-01',p.job_id,
          NULL::uuid,r.purpose,'RUNNING','SUCCEEDED')
        OR a.occurred_at<p.created_at OR a.occurred_at>NEW.published_at THEN
        RAISE EXCEPTION 'Audit result publication source mismatch'; END IF;
      IF c.member_count=0 AND (NEW.byte_count<>0 OR NEW.file_sha256<>sha256(''::bytea)) THEN
        RAISE EXCEPTION 'Audit result empty file mismatch'; END IF;
      IF c.member_count>0 AND NEW.byte_count<c.member_count THEN
        RAISE EXCEPTION 'Audit result nonempty file mismatch'; END IF;
      expected=jsonb_build_object(
        'manifest_version',NEW.manifest_version,'export_id',r.export_id::text,'actor_id',r.actor_id::text,
        'scope',r.scope,'project_id',r.project_id::text,'purpose',r.purpose,
        'requested_at',to_char(r.requested_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'captured_at',to_char(c.captured_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'start_at',to_char(r.start_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'end_at',to_char(r.end_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        'filters',jsonb_build_object('action',r.action,'outcome',r.outcome,'actor_id',r.filter_actor_id::text,
          'target_object_type',r.target_object_type,'target_object_id',r.target_object_id::text,'trace_id',r.filter_trace_id::text),
        'intent_hash',r.intent_hash,'policy_version',r.policy_version,'projection_version',r.projection_version,
        'format_version',r.format_version,'membership_version',c.membership_version,
        'member_count',c.member_count,'membership_sha256',c.membership_hash,
        'file_sha256',encode(NEW.file_sha256,'hex'),'byte_count',NEW.byte_count);
      -- All whitelisted manifest values are safe ASCII codes, UUIDs, timestamps or integers.
      -- Reconstruct sorted compact JSON bytes; never parse untrusted bytes as authority.
      SELECT '{'||string_agg(to_json(k)::text||':'||CASE WHEN k='filters' THEN
          (SELECT '{'||string_agg(to_json(fk)::text||':'||fv::text,',' ORDER BY fk COLLATE "C")||'}'
             FROM jsonb_each(v) AS filters(fk,fv))
          ELSE v::text END,',' ORDER BY k COLLATE "C")||'}'||chr(10)
        INTO canonical FROM jsonb_each(expected) AS fields(k,v);
      IF NEW.manifest_bytes<>convert_to(canonical,'UTF8') THEN
        RAISE EXCEPTION 'Audit result canonical manifest mismatch'; END IF;
      RETURN NEW;
    END; $$;
    CREATE TRIGGER trg_aud_export_results_insert BEFORE INSERT ON plm.aud_export_results
      FOR EACH ROW EXECUTE FUNCTION plm.guard_audit_export_result();
    CREATE TRIGGER trg_aud_export_results_immutable BEFORE UPDATE OR DELETE ON plm.aud_export_results
      FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_export_mutation();
    CREATE TRIGGER trg_aud_export_results_no_truncate BEFORE TRUNCATE ON plm.aud_export_results
      FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_export_mutation();
    """)


def downgrade():
    if context.is_offline_mode():raise RuntimeError('offline Audit result downgrade disabled')
    op.execute('LOCK TABLE plm.aud_export_results IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM plm.aud_export_results)')):
        raise RuntimeError('Audit result history exists; downgrade refused')
    op.drop_table('aud_export_results',schema='plm')
    op.execute('DROP FUNCTION plm.guard_audit_export_result()')
