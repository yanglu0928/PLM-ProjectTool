"""CR-AUD-001 immutable export intent and transactional membership seal."""
from alembic import context, op
import sqlalchemy as sa

revision = "20260926_0037"
down_revision = "20260926_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE plm.aud_exports (
        export_id uuid CONSTRAINT pk_aud_exports PRIMARY KEY DEFAULT uuidv7(),
        actor_id uuid NOT NULL CONSTRAINT fk_aud_exports__actor_id__auth_users REFERENCES plm.auth_users(user_id),
        scope text NOT NULL, project_id uuid CONSTRAINT fk_aud_exports__project_id__prj_projects REFERENCES plm.prj_projects(project_id),
        trace_id uuid NOT NULL, requested_at timestamptz(6) NOT NULL DEFAULT statement_timestamp(),
        purpose text NOT NULL, start_at timestamptz(6) NOT NULL, end_at timestamptz(6) NOT NULL,
        action text, outcome text, filter_actor_id uuid, target_object_type text,
        target_object_id uuid, filter_trace_id uuid,
        policy_version text NOT NULL, projection_version text NOT NULL, format_version text NOT NULL,
        intent_hash text NOT NULL,
        CONSTRAINT ck_aud_exports__scope CHECK (
            (scope='DEPLOYMENT' AND project_id IS NULL) OR
            (scope='PROJECT' AND project_id IS NOT NULL AND project_id<>'00000000-0000-0000-0000-000000000000'::uuid)),
        CONSTRAINT ck_aud_exports__purpose CHECK (purpose IN ('SECURITY_REVIEW','COMPLIANCE_REVIEW','PROJECT_GOVERNANCE','INCIDENT_INVESTIGATION') AND NOT(scope='DEPLOYMENT' AND purpose='PROJECT_GOVERNANCE')),
        CONSTRAINT ck_aud_exports__window CHECK (start_at>=timestamptz '0001-01-01 00:00:00+00' AND end_at<timestamptz '10000-01-01 00:00:00+00' AND start_at<end_at AND end_at-start_at<=interval '31 days' AND isfinite(requested_at)),
        CONSTRAINT ck_aud_exports__filters CHECK ((action IS NULL OR action ~ '^[A-Z][A-Z0-9_]{0,63}$') AND (outcome IS NULL OR outcome IN ('SUCCESS','DENIED','FAILED')) AND (target_object_type IS NULL OR target_object_type ~ '^[A-Z]{2,3}-[0-9]{2}$')),
        CONSTRAINT ck_aud_exports__versions CHECK (policy_version='AUDIT-EXPORT-POLICY-V1' AND projection_version='AUDIT-EVENT-SAFE-V1' AND format_version='JSONL_V1' AND intent_hash ~ '^[0-9a-f]{64}$'),
        CONSTRAINT ck_aud_exports__uuid CHECK (export_id<>'00000000-0000-0000-0000-000000000000'::uuid AND actor_id<>'00000000-0000-0000-0000-000000000000'::uuid AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid AND (filter_actor_id IS NULL OR filter_actor_id<>'00000000-0000-0000-0000-000000000000'::uuid) AND (target_object_id IS NULL OR target_object_id<>'00000000-0000-0000-0000-000000000000'::uuid) AND (filter_trace_id IS NULL OR filter_trace_id<>'00000000-0000-0000-0000-000000000000'::uuid))
    );
    CREATE TABLE plm.aud_export_members (
        export_id uuid NOT NULL CONSTRAINT fk_aud_export_members__export_id__aud_exports REFERENCES plm.aud_exports(export_id),
        position bigint NOT NULL, event_id uuid NOT NULL CONSTRAINT fk_aud_export_members__event_id__aud_events REFERENCES plm.aud_events(audit_event_id),
        occurred_at timestamptz(6) NOT NULL, created_xid bigint NOT NULL DEFAULT txid_current(),
        CONSTRAINT pk_aud_export_members PRIMARY KEY(export_id,position), CONSTRAINT uq_aud_export_members__export_id_event_id UNIQUE(export_id,event_id),
        CONSTRAINT ck_aud_export_members__position CHECK(position>=1)
    );
    CREATE TABLE plm.aud_export_captures (
        export_id uuid CONSTRAINT pk_aud_export_captures PRIMARY KEY CONSTRAINT fk_aud_export_captures__export_id__aud_exports REFERENCES plm.aud_exports(export_id),
        captured_at timestamptz(6) NOT NULL DEFAULT statement_timestamp(),
        member_count bigint NOT NULL, membership_hash text NOT NULL, membership_version text NOT NULL,
        created_xid bigint NOT NULL DEFAULT txid_current(),
        CONSTRAINT ck_aud_export_captures__shape CHECK(member_count>=0 AND membership_hash ~ '^[0-9a-f]{64}$' AND membership_version='CAPTURE-MEMBERSHIP-V1' AND isfinite(captured_at))
    );
    """)
    op.execute("""
    CREATE FUNCTION plm.guard_audit_export_member() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r plm.aud_exports%ROWTYPE;
    BEGIN
        SELECT * INTO STRICT r FROM plm.aud_exports WHERE export_id=NEW.export_id FOR UPDATE;
        IF EXISTS(SELECT 1 FROM plm.aud_export_captures WHERE export_id=NEW.export_id) THEN
            RAISE EXCEPTION 'Audit capture already sealed'; END IF;
        IF NOT EXISTS(SELECT 1 FROM plm.aud_events e WHERE e.audit_event_id=NEW.event_id
            AND e.occurred_at=NEW.occurred_at AND e.event_scope=r.scope
            AND e.target_project_id IS NOT DISTINCT FROM r.project_id
            AND e.occurred_at>=r.start_at AND e.occurred_at<r.end_at
            AND (r.action IS NULL OR e.action=r.action)
            AND (r.outcome IS NULL OR e.outcome=r.outcome)
            AND (r.filter_actor_id IS NULL OR e.actor_id=r.filter_actor_id)
            AND (r.target_object_type IS NULL OR e.target_object_type=r.target_object_type)
            AND (r.target_object_id IS NULL OR e.target_object_id=r.target_object_id)
            AND (r.filter_trace_id IS NULL OR e.trace_id=r.filter_trace_id)) THEN
            RAISE EXCEPTION 'Audit capture source mismatch'; END IF;
        NEW.created_xid=txid_current(); RETURN NEW;
    END; $$;
    CREATE FUNCTION plm.guard_audit_export_seal() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r plm.aud_exports%ROWTYPE; n bigint; body text; invalid boolean;
    BEGIN
        SELECT * INTO STRICT r FROM plm.aud_exports WHERE export_id=NEW.export_id FOR UPDATE;
        IF NEW.captured_at<r.requested_at THEN RAISE EXCEPTION 'Audit capture time mismatch'; END IF;
        SELECT count(*), coalesce(string_agg(event_id::text||'|'||
            to_char(occurred_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')||chr(10),'' ORDER BY position),'')
            INTO n,body FROM plm.aud_export_members WHERE export_id=NEW.export_id;
        SELECT coalesce(bool_or(position<>rank OR created_xid<>txid_current()),false) INTO invalid
            FROM (SELECT position,created_xid,row_number() OVER(ORDER BY occurred_at DESC,event_id DESC) rank
                FROM plm.aud_export_members WHERE export_id=NEW.export_id) m;
        IF invalid OR n<>NEW.member_count OR NEW.membership_hash<>
            encode(sha256(convert_to('PLM-AUDIT-CAPTURE-MEMBERSHIP-V1','UTF8')||decode('00','hex')||convert_to(body,'UTF8')),'hex') THEN
            RAISE EXCEPTION 'Audit capture completeness mismatch'; END IF;
        NEW.created_xid=txid_current(); RETURN NEW;
    END; $$;
    CREATE FUNCTION plm.require_audit_export_seal() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NOT EXISTS(SELECT 1 FROM plm.aud_export_captures WHERE export_id=NEW.export_id AND created_xid=NEW.created_xid) THEN
            RAISE EXCEPTION 'Audit capture must seal in member transaction'; END IF;
        RETURN NULL;
    END; $$;
    CREATE FUNCTION plm.reject_audit_export_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Audit export history is immutable'; END; $$;
    CREATE TRIGGER trg_aud_export_members_insert BEFORE INSERT ON plm.aud_export_members
        FOR EACH ROW EXECUTE FUNCTION plm.guard_audit_export_member();
    CREATE TRIGGER trg_aud_export_captures_insert BEFORE INSERT ON plm.aud_export_captures
        FOR EACH ROW EXECUTE FUNCTION plm.guard_audit_export_seal();
    CREATE CONSTRAINT TRIGGER trg_aud_export_members_seal AFTER INSERT ON plm.aud_export_members
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.require_audit_export_seal();
    """)
    for table in ("aud_exports", "aud_export_members", "aud_export_captures"):
        op.execute(f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.reject_audit_export_mutation()")
        op.execute(f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.reject_audit_export_mutation()")


def downgrade():
    if context.is_offline_mode():
        raise RuntimeError("offline Audit export downgrade disabled")
    op.execute("LOCK TABLE plm.aud_exports, plm.aud_export_members, plm.aud_export_captures IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.aud_exports) OR EXISTS(SELECT 1 FROM plm.aud_export_members) OR EXISTS(SELECT 1 FROM plm.aud_export_captures)")):
        raise RuntimeError("Audit export history exists; downgrade refused")
    for table in ("aud_export_members", "aud_export_captures", "aud_exports"):
        op.drop_table(table, schema="plm")
    for name in ("require_audit_export_seal", "guard_audit_export_seal", "guard_audit_export_member", "reject_audit_export_mutation"):
        op.execute(f"DROP FUNCTION plm.{name}()")
