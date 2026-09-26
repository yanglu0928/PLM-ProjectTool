"""CR-WFL-004 immutable Checklist record chain; no actual Gate/Owner proof."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0032"
down_revision = "20260926_0031"
branch_labels = None
depends_on = None

def _make_tables(create):
    ident = postgresql.UUID(as_uuid=True)
    time = postgresql.TIMESTAMP(timezone=True, precision=6)
    def col(name, kind=sa.Text(), nullable=False, **kwargs):
        return sa.Column(name, kind, nullable=nullable, **kwargs)
    def pk(name):
        return sa.Column(name, ident, primary_key=True, server_default=sa.text("uuidv7()"))
    def check(name, expression):
        return sa.CheckConstraint(expression, name=name)
    def fk(name, cols, targets):
        return sa.ForeignKeyConstraint(cols, targets, name=name, ondelete="NO ACTION")
    def unique(name, *cols):
        return sa.UniqueConstraint(*cols, name=name)
    def nonzero(name, *cols):
        return check(name, " AND ".join(c + "<>'00000000-0000-0000-0000-000000000000'::uuid" for c in cols))
    record = create(
        "wfl_checklist_records", pk("record_id"), col("workflow_id", ident), col("project_id", ident),
        col("definition_version", sa.Integer()), col("stage_key"), col("item_key"), col("observed_stage_state"),
        col("before_state"), col("result"),
        col("before_item_version", sa.BigInteger()), col("after_item_version", sa.BigInteger()),
        col("before_workflow_version", sa.BigInteger()), col("after_workflow_version", sa.BigInteger()),
        col("supersedes_record_id", ident, nullable=True), col("actor_id", ident), col("trace_id", ident),
        col("occurred_at", time), col("reason", nullable=True), col("impact", nullable=True),
        col("content_fingerprint", sa.LargeBinary()),
        col("created_xid", sa.BigInteger(), server_default=sa.text("txid_current()")),
        fk("fk_wfl_records__workflow", ["workflow_id","project_id"],
           ["plm.wfl_project_workflows.workflow_id","plm.wfl_project_workflows.project_id"]),
        fk("fk_wfl_records__item", ["workflow_id","item_key"],
           ["plm.wfl_checklist_items.workflow_id","plm.wfl_checklist_items.item_key"]),
        fk("fk_wfl_records__stage", ["workflow_id","stage_key"],
           ["plm.wfl_stages.workflow_id","plm.wfl_stages.stage_key"]),
        fk("fk_wfl_records__actor", ["actor_id"], ["plm.auth_users.user_id"]),
        unique("uq_wfl_records__id_scope_item", "record_id","workflow_id","project_id","item_key"),
        unique("uq_wfl_records__item_version", "workflow_id","item_key","after_item_version"),
        fk("fk_wfl_records__supersedes", ["supersedes_record_id","workflow_id","project_id","item_key"],
           ["plm.wfl_checklist_records."+c for c in ("record_id","workflow_id","project_id","item_key")]),
        check("ck_wfl_records__version", "definition_version=1 AND before_item_version>=0 AND after_item_version=before_item_version+1 AND before_workflow_version>=0 AND after_workflow_version=before_workflow_version+1"),
        check("ck_wfl_records__stage_state", "observed_stage_state IN ('ACTIVE','BLOCKED')"),
        check("ck_wfl_records__state", "before_state IN ('PENDING','PASS','FAIL','WAIVED') AND result IN ('PASS','FAIL','WAIVED')"),
        check("ck_wfl_records__chain", "(before_item_version=0 AND before_state='PENDING' AND supersedes_record_id IS NULL) OR (before_item_version>0 AND before_state<>'PENDING' AND supersedes_record_id IS NOT NULL AND supersedes_record_id<>record_id)"),
        check("ck_wfl_records__details", "(reason IS NULL OR (char_length(reason) BETWEEN 1 AND 2000 AND char_length(btrim(reason,chr(9)||chr(10)||chr(11)||chr(12)||chr(13)||chr(28)||chr(29)||chr(30)||chr(31)||chr(32)||chr(133)||chr(160)||chr(5760)||chr(8192)||chr(8193)||chr(8194)||chr(8195)||chr(8196)||chr(8197)||chr(8198)||chr(8199)||chr(8200)||chr(8201)||chr(8202)||chr(8232)||chr(8233)||chr(8239)||chr(8287)||chr(12288)))>0)) AND (impact IS NULL OR (char_length(impact) BETWEEN 1 AND 2000 AND char_length(btrim(impact,chr(9)||chr(10)||chr(11)||chr(12)||chr(13)||chr(28)||chr(29)||chr(30)||chr(31)||chr(32)||chr(133)||chr(160)||chr(5760)||chr(8192)||chr(8193)||chr(8194)||chr(8195)||chr(8196)||chr(8197)||chr(8198)||chr(8199)||chr(8200)||chr(8201)||chr(8202)||chr(8232)||chr(8233)||chr(8239)||chr(8287)||chr(12288)))>0)) AND (result<>'WAIVED' OR (reason IS NOT NULL AND impact IS NOT NULL))"),
        check("ck_wfl_records__fingerprint", "octet_length(content_fingerprint)=32 AND created_xid>0"),
        nonzero("ck_wfl_records__uuid", "record_id","workflow_id","project_id","actor_id","trace_id"),
        sa.Index("ix_wfl_records__project_history", "project_id","occurred_at","record_id"),
        schema="plm",
    )
    refs = create(
        "wfl_checklist_record_refs", pk("record_ref_id"),
        col("record_id", ident), col("workflow_id", ident), col("project_id", ident), col("item_key"),
        col("ref_kind"), col("ref_id", ident), col("ref_scope"), col("ref_project_id", ident, nullable=True),
        col("observed_state"), col("observed_lock_version", sa.BigInteger()),
        col("content_fingerprint", sa.LargeBinary()), col("verified_at", time),
        col("proof_schema_version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("evidence_id", ident, sa.Computed("CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END", persisted=True)),
        fk("fk_wfl_record_refs__record", ["record_id","workflow_id","project_id","item_key"],
           ["plm.wfl_checklist_records."+c for c in ("record_id","workflow_id","project_id","item_key")]),
        fk("fk_wfl_record_refs__evidence", ["evidence_id"], ["plm.evd_evidence_records.evidence_id"]),
        unique("uq_wfl_record_refs__target", "record_id","ref_kind","ref_id"),
        check("ck_wfl_record_refs__kind", "ref_kind IN ('EVIDENCE','REVIEW_ROUND','APPROVED_EXCEPTION')"),
        check("ck_wfl_record_refs__scope", "(ref_scope='PROJECT' AND ref_project_id IS NOT NULL AND ref_project_id=project_id) OR (ref_kind='EVIDENCE' AND ref_scope='GLOBAL' AND ref_project_id IS NULL)"),
        check("ck_wfl_record_refs__state", "(ref_kind='EVIDENCE' AND observed_state IN ('CANDIDATE','ELIGIBLE','INELIGIBLE','REVOKED')) OR (ref_kind='REVIEW_ROUND' AND observed_state IN ('PENDING','IN_REVIEW','APPROVED','RETURNED','WITHDRAWN')) OR (ref_kind='APPROVED_EXCEPTION' AND observed_state='APPROVED')"),
        check("ck_wfl_record_refs__version", "observed_lock_version>=0 AND proof_schema_version=1 AND octet_length(content_fingerprint)=32"),
        nonzero("ck_wfl_record_refs__uuid", "record_ref_id","record_id","workflow_id","project_id","ref_id"),
        sa.Index("ix_wfl_record_refs__target", "ref_kind","ref_id","record_id"),
        schema="plm",
    )
    return record, refs

_TABLES = ("wfl_checklist_records", "wfl_checklist_record_refs")
_GUARDS = """
CREATE FUNCTION plm.guard_checklist_record() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root plm.wfl_checklist_records%ROWTYPE; previous plm.wfl_checklist_records%ROWTYPE;
        w plm.wfl_project_workflows%ROWTYPE; ev plm.evd_evidence_records%ROWTYPE;
        item_state text; item_version bigint; item_stage text; stage_state text;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Checklist history immutable'; END IF;
 IF TG_TABLE_NAME='wfl_checklist_records' THEN
   SELECT * INTO w FROM plm.wfl_project_workflows WHERE workflow_id=NEW.workflow_id FOR UPDATE;
   IF NOT FOUND OR w.project_id IS DISTINCT FROM NEW.project_id OR w.workflow_state<>'ACTIVE'
      OR w.current_stage_key IS DISTINCT FROM NEW.stage_key OR w.lock_version IS DISTINCT FROM NEW.before_workflow_version
      OR w.workflow_version IS DISTINCT FROM NEW.definition_version THEN
     RAISE EXCEPTION 'Checklist Workflow current facts mismatch'; END IF;
   SELECT i.item_state,i.lock_version,s.stage_key,s.stage_state INTO item_state,item_version,item_stage,stage_state
   FROM plm.wfl_checklist_items i
   JOIN plm.wfl_stage_checklists c USING(stage_checklist_id,workflow_id,project_id)
   JOIN plm.wfl_stages s USING(stage_id,workflow_id,project_id)
   WHERE i.workflow_id=NEW.workflow_id AND i.item_key=NEW.item_key FOR UPDATE OF i FOR SHARE OF s;
   IF NOT FOUND OR item_state IS DISTINCT FROM NEW.before_state OR item_version IS DISTINCT FROM NEW.before_item_version
      OR item_stage IS DISTINCT FROM NEW.stage_key OR stage_state NOT IN ('ACTIVE','BLOCKED') THEN
     RAISE EXCEPTION 'Checklist Item current facts mismatch'; END IF;
   IF NEW.before_item_version=0 THEN
     IF NEW.before_state<>'PENDING' OR NEW.supersedes_record_id IS NOT NULL THEN
       RAISE EXCEPTION 'Checklist first record invalid'; END IF;
   ELSE
     SELECT * INTO previous FROM plm.wfl_checklist_records
       WHERE workflow_id=NEW.workflow_id AND project_id=NEW.project_id AND item_key=NEW.item_key
             AND after_item_version=NEW.before_item_version;
     IF NOT FOUND OR previous.record_id IS DISTINCT FROM NEW.supersedes_record_id
        OR previous.result IS DISTINCT FROM NEW.before_state THEN
       RAISE EXCEPTION 'Checklist trusted previous record missing'; END IF;
   END IF;
   NEW.created_xid:=txid_current();
   NEW.observed_stage_state:=stage_state;
 ELSE
   SELECT * INTO root FROM plm.wfl_checklist_records WHERE record_id=NEW.record_id;
   IF NOT FOUND OR root.created_xid<>txid_current() OR root.workflow_id IS DISTINCT FROM NEW.workflow_id
      OR root.project_id IS DISTINCT FROM NEW.project_id OR root.item_key IS DISTINCT FROM NEW.item_key THEN
      RAISE EXCEPTION 'Checklist snapshot sealed or parent mismatch'; END IF;
   PERFORM 1 FROM plm.wfl_project_workflows WHERE workflow_id=root.workflow_id FOR UPDATE;
   IF NEW.ref_kind='EVIDENCE' THEN
     SELECT * INTO ev FROM plm.evd_evidence_records WHERE evidence_id=NEW.ref_id FOR SHARE;
     IF NOT FOUND OR ev.scope IS DISTINCT FROM NEW.ref_scope OR ev.project_id IS DISTINCT FROM NEW.ref_project_id
        OR ev.eligibility_state IS DISTINCT FROM NEW.observed_state OR ev.lock_version IS DISTINCT FROM NEW.observed_lock_version
        OR ev.content_fingerprint IS DISTINCT FROM NEW.content_fingerprint THEN
       RAISE EXCEPTION 'Checklist Evidence observed facts mismatch'; END IF;
   END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION plm.validate_checklist_record() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root plm.wfl_checklist_records%ROWTYPE; w plm.wfl_project_workflows%ROWTYPE;
        item_state text; item_version bigint; stage_state text;
BEGIN
 SELECT * INTO root FROM plm.wfl_checklist_records WHERE record_id=NEW.record_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Checklist history parent missing'; END IF;
 SELECT * INTO w FROM plm.wfl_project_workflows WHERE workflow_id=root.workflow_id FOR UPDATE;
 SELECT i.item_state,i.lock_version,s.stage_state INTO item_state,item_version,stage_state
 FROM plm.wfl_checklist_items i JOIN plm.wfl_stage_checklists c USING(stage_checklist_id,workflow_id,project_id)
 JOIN plm.wfl_stages s USING(stage_id,workflow_id,project_id)
 WHERE i.workflow_id=root.workflow_id AND i.item_key=root.item_key;
 IF w.workflow_state<>'ACTIVE' OR w.current_stage_key IS DISTINCT FROM root.stage_key
    OR w.lock_version IS DISTINCT FROM root.after_workflow_version
    OR item_state IS DISTINCT FROM root.result OR item_version IS DISTINCT FROM root.after_item_version
    OR stage_state IS DISTINCT FROM root.observed_stage_state THEN
    RAISE EXCEPTION 'Checklist history/projection atomicity invalid'; END IF;
 IF root.result IN ('PASS','WAIVED') THEN
   IF NOT EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs WHERE record_id=root.record_id AND ref_kind='EVIDENCE')
      OR NOT EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs WHERE record_id=root.record_id AND ref_kind='REVIEW_ROUND')
      OR EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs WHERE record_id=root.record_id AND
                ((ref_kind='EVIDENCE' AND observed_state<>'ELIGIBLE')
                 OR (ref_kind='REVIEW_ROUND' AND observed_state<>'APPROVED'))) THEN
     RAISE EXCEPTION 'Checklist positive basis incomplete'; END IF;
 END IF;
 IF (root.result='WAIVED' AND NOT EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs WHERE record_id=root.record_id AND ref_kind='APPROVED_EXCEPTION'))
    OR (root.result<>'WAIVED' AND EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs WHERE record_id=root.record_id AND ref_kind='APPROVED_EXCEPTION')) THEN
     RAISE EXCEPTION 'Checklist exception basis invalid'; END IF;
 IF EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs r
           JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id WHERE r.record_id=root.record_id AND
            (r.ref_scope IS DISTINCT FROM e.scope OR r.ref_project_id IS DISTINCT FROM e.project_id
             OR r.observed_state IS DISTINCT FROM e.eligibility_state OR r.observed_lock_version IS DISTINCT FROM e.lock_version
             OR r.content_fingerprint IS DISTINCT FROM e.content_fingerprint)) THEN
      RAISE EXCEPTION 'Checklist Evidence facts changed before commit'; END IF;
 RETURN NULL;
END; $$;
"""

def upgrade() -> None:
    _make_tables(op.create_table)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}_guard BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_checklist_record()")
        op.execute(f"CREATE TRIGGER trg_{table}_truncate BEFORE TRUNCATE ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_checklist_record()")
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_{table}_complete AFTER INSERT ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.validate_checklist_record()")

def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Checklist history downgrade disabled")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.wfl_checklist_records) OR EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs)")):
        raise RuntimeError("Checklist history exists; downgrade refused")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_checklist_record()")
    op.execute("DROP FUNCTION plm.guard_checklist_record()")
