"""CR-WFL-003 frozen history structure; not business Gate/Owner authorization."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0031"
down_revision = "20260926_0030"
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
    def parent(name, key, table):
        return fk(name, [key, "workflow_id", "project_id"],
                  ["plm." + table + "." + c for c in (key, "workflow_id", "project_id")])
    def nonzero(name, *cols):
        return check(name, " AND ".join(c + "<>'00000000-0000-0000-0000-000000000000'::uuid" for c in cols))
    transition = create(
        "wfl_stage_transitions", pk("stage_transition_id"),
        col("workflow_id", ident), col("project_id", ident),
        col("definition_version", sa.Integer()), col("definition_fingerprint", sa.LargeBinary()),
        col("transition_type"), col("from_stage"), col("to_stage"),
        col("before_lock_version", sa.BigInteger()), col("after_lock_version", sa.BigInteger()),
        col("actor_id", ident), col("reason"), col("occurred_at", time),
        col("trace_id", ident), col("gate_fingerprint", sa.LargeBinary()),
        col("created_xid", sa.BigInteger(), server_default=sa.text("txid_current()")),
        fk("fk_wfl_transitions__workflow", ["workflow_id", "project_id"],
           ["plm.wfl_project_workflows.workflow_id", "plm.wfl_project_workflows.project_id"]),
        fk("fk_wfl_transitions__from", ["workflow_id", "from_stage"],
           ["plm.wfl_stages.workflow_id", "plm.wfl_stages.stage_key"]),
        fk("fk_wfl_transitions__to", ["workflow_id", "to_stage"],
           ["plm.wfl_stages.workflow_id", "plm.wfl_stages.stage_key"]),
        fk("fk_wfl_transitions__actor", ["actor_id"], ["plm.auth_users.user_id"]),
        unique("uq_wfl_transitions__id_workflow_project", "stage_transition_id", "workflow_id", "project_id"),
        unique("uq_wfl_transitions__version", "workflow_id", "after_lock_version"),
        check("ck_wfl_transitions__definition", "definition_version=1 AND definition_fingerprint=decode('4bcda512e4c0d26a9766bdb41d9086a73a6d187db61d319ff94a1e929c3802a9','hex')"),
        check("ck_wfl_transitions__pair", "transition_type='FORWARD' AND ((from_stage='HANDOVER' AND to_stage='SURVEY') OR (from_stage='SURVEY' AND to_stage='REQUIREMENT') OR (from_stage='REQUIREMENT' AND to_stage='PROTOTYPE') OR (from_stage='PROTOTYPE' AND to_stage='SOLUTION') OR (from_stage='SOLUTION' AND to_stage='PLAN'))"),
        check("ck_wfl_transitions__versions", "before_lock_version>=0 AND after_lock_version=before_lock_version+1"),
        check("ck_wfl_transitions__reason", "char_length(reason) BETWEEN 1 AND 2000 AND char_length(btrim(reason))>0"),
        check("ck_wfl_transitions__hash", "octet_length(gate_fingerprint)=32"),
        check("ck_wfl_transitions__xid", "created_xid>0"),
        nonzero("ck_wfl_transitions__uuid", "stage_transition_id", "workflow_id", "project_id", "actor_id", "trace_id"),
        sa.Index("ix_wfl_transitions__history", "project_id", "occurred_at", "stage_transition_id"),
        schema="plm",
    )
    items = create(
        "wfl_transition_gate_items", pk("gate_item_id"),
        col("stage_transition_id", ident), col("workflow_id", ident), col("project_id", ident),
        col("item_key"), col("required", sa.Boolean()), col("result"),
        col("evidence_policy_ref"), col("review_policy_ref"),
        col("waiver_actor_id", ident, nullable=True),
        col("waiver_reason", nullable=True), col("waiver_impact", nullable=True),
        parent("fk_wfl_gate_items__transition", "stage_transition_id", "wfl_stage_transitions"),
        fk("fk_wfl_gate_items__item", ["workflow_id", "item_key"],
           ["plm.wfl_checklist_items.workflow_id", "plm.wfl_checklist_items.item_key"]),
        fk("fk_wfl_gate_items__waiver_actor", ["waiver_actor_id"], ["plm.auth_users.user_id"]),
        unique("uq_wfl_gate_items__id_workflow_project", "gate_item_id", "workflow_id", "project_id"),
        unique("uq_wfl_gate_items__key", "stage_transition_id", "item_key"),
        check("ck_wfl_gate_items__result", "required AND result IN ('PASS','WAIVED')"),
        check("ck_wfl_gate_items__waiver", "(result='PASS' AND waiver_actor_id IS NULL AND waiver_reason IS NULL AND waiver_impact IS NULL) OR (result='WAIVED' AND waiver_actor_id IS NOT NULL AND waiver_actor_id<>'00000000-0000-0000-0000-000000000000'::uuid AND waiver_reason IS NOT NULL AND waiver_impact IS NOT NULL AND char_length(waiver_reason) BETWEEN 1 AND 2000 AND char_length(btrim(waiver_reason))>0 AND char_length(waiver_impact) BETWEEN 1 AND 2000 AND char_length(btrim(waiver_impact))>0)"),
        nonzero("ck_wfl_gate_items__uuid", "gate_item_id", "stage_transition_id", "workflow_id", "project_id"),
        schema="plm",
    )
    refs = create(
        "wfl_transition_gate_refs", pk("gate_ref_id"),
        col("gate_item_id", ident), col("workflow_id", ident), col("project_id", ident),
        col("ref_kind"), col("ref_id", ident), col("ref_scope"),
        col("ref_project_id", ident, nullable=True),
        col("observed_state"), col("observed_lock_version", sa.BigInteger()),
        col("content_fingerprint", sa.LargeBinary()), col("verified_at", time),
        col("proof_schema_version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("evidence_id", ident, sa.Computed("CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END", persisted=True)),
        parent("fk_wfl_gate_refs__item", "gate_item_id", "wfl_transition_gate_items"),
        fk("fk_wfl_gate_refs__evidence", ["evidence_id"], ["plm.evd_evidence_records.evidence_id"]),
        unique("uq_wfl_gate_refs__identity", "gate_item_id", "ref_kind", "ref_id"),
        check("ck_wfl_gate_refs__kind", "ref_kind IN ('EVIDENCE','REVIEW_ROUND','APPROVED_EXCEPTION')"),
        check("ck_wfl_gate_refs__scope", "(ref_scope='PROJECT' AND ref_project_id IS NOT NULL AND ref_project_id=project_id) OR (ref_kind='EVIDENCE' AND ref_scope='GLOBAL' AND ref_project_id IS NULL)"),
        check("ck_wfl_gate_refs__state", "(ref_kind='EVIDENCE' AND observed_state='ELIGIBLE') OR (ref_kind IN ('REVIEW_ROUND','APPROVED_EXCEPTION') AND observed_state='APPROVED')"),
        check("ck_wfl_gate_refs__version_hash", "observed_lock_version>=0 AND proof_schema_version=1 AND octet_length(content_fingerprint)=32"),
        nonzero("ck_wfl_gate_refs__uuid", "gate_ref_id", "gate_item_id", "workflow_id", "project_id", "ref_id"),
        sa.Index("ix_wfl_gate_refs__target", "ref_kind", "ref_id", "gate_item_id"),
        schema="plm",
    )
    return transition, items, refs

_TABLES = ("wfl_stage_transitions", "wfl_transition_gate_items", "wfl_transition_gate_refs")
_GUARDS = """
CREATE FUNCTION plm.guard_workflow_history() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root plm.wfl_stage_transitions%ROWTYPE; w plm.wfl_project_workflows%ROWTYPE; ev plm.evd_evidence_records%ROWTYPE;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Workflow success history immutable'; END IF;
 IF TG_TABLE_NAME='wfl_stage_transitions' THEN
   SELECT * INTO w FROM plm.wfl_project_workflows WHERE workflow_id=NEW.workflow_id FOR UPDATE;
   IF NOT FOUND OR w.project_id IS DISTINCT FROM NEW.project_id OR w.workflow_state<>'ACTIVE'
      OR w.current_stage_key IS DISTINCT FROM NEW.from_stage OR w.lock_version IS DISTINCT FROM NEW.before_lock_version
      OR w.definition_fingerprint IS DISTINCT FROM NEW.definition_fingerprint THEN
     RAISE EXCEPTION 'Workflow history current facts mismatch'; END IF;
   NEW.created_xid:=txid_current();
 ELSE
   IF TG_TABLE_NAME='wfl_transition_gate_items' THEN
     SELECT * INTO root FROM plm.wfl_stage_transitions WHERE stage_transition_id=NEW.stage_transition_id;
   ELSE
     SELECT t.* INTO root FROM plm.wfl_stage_transitions t JOIN plm.wfl_transition_gate_items i USING(stage_transition_id,workflow_id,project_id) WHERE i.gate_item_id=NEW.gate_item_id;
   END IF;
   IF NOT FOUND OR root.created_xid<>txid_current() OR root.workflow_id IS DISTINCT FROM NEW.workflow_id OR root.project_id IS DISTINCT FROM NEW.project_id THEN
      RAISE EXCEPTION 'Workflow snapshot sealed or parent mismatch'; END IF;
   PERFORM 1 FROM plm.wfl_project_workflows WHERE workflow_id=root.workflow_id FOR UPDATE;
   IF TG_TABLE_NAME='wfl_transition_gate_refs' THEN
    IF NEW.ref_kind='EVIDENCE' THEN
     SELECT * INTO ev FROM plm.evd_evidence_records WHERE evidence_id=NEW.ref_id FOR SHARE;
     IF NOT FOUND OR ev.scope IS DISTINCT FROM NEW.ref_scope OR ev.project_id IS DISTINCT FROM NEW.ref_project_id
        OR ev.eligibility_state IS DISTINCT FROM NEW.observed_state OR ev.lock_version IS DISTINCT FROM NEW.observed_lock_version
        OR ev.content_fingerprint IS DISTINCT FROM NEW.content_fingerprint THEN
       RAISE EXCEPTION 'Workflow Evidence observed facts mismatch'; END IF;
    END IF;
   END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION plm.validate_workflow_history() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE root plm.wfl_stage_transitions%ROWTYPE; root_id uuid; w plm.wfl_project_workflows%ROWTYPE; expected text[];
BEGIN
 IF TG_TABLE_NAME IN ('wfl_stage_transitions','wfl_transition_gate_items') THEN root_id:=NEW.stage_transition_id;
 ELSE SELECT stage_transition_id INTO root_id FROM plm.wfl_transition_gate_items WHERE gate_item_id=NEW.gate_item_id;
 END IF;
 SELECT * INTO root FROM plm.wfl_stage_transitions WHERE stage_transition_id=root_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Workflow history parent missing'; END IF;
 SELECT * INTO w FROM plm.wfl_project_workflows WHERE workflow_id=root.workflow_id FOR UPDATE;
 IF w.workflow_state<>'ACTIVE' OR w.current_stage_key IS DISTINCT FROM root.to_stage OR w.lock_version IS DISTINCT FROM root.after_lock_version
    OR NOT EXISTS(SELECT 1 FROM plm.wfl_stages WHERE workflow_id=root.workflow_id AND stage_key=root.from_stage AND stage_state='COMPLETED')
    OR NOT EXISTS(SELECT 1 FROM plm.wfl_stages WHERE workflow_id=root.workflow_id AND stage_key=root.to_stage AND stage_state='ACTIVE') THEN
    RAISE EXCEPTION 'Workflow history/state atomicity invalid'; END IF;
 expected:=CASE root.from_stage
   WHEN 'HANDOVER' THEN ARRAY['HANDOVER_BASELINE','HANDOVER_ISSUES']
   WHEN 'SURVEY' THEN ARRAY['SURVEY_ACTUAL_SOURCES','SURVEY_CONCLUSION']
   WHEN 'REQUIREMENT' THEN ARRAY['REQUIREMENT_ACCEPTANCE','REQUIREMENT_FORMAL_VERSIONS']
   WHEN 'PROTOTYPE' THEN ARRAY['PROTOTYPE_COVERAGE','PROTOTYPE_SCOPE_DECISIONS']
   WHEN 'SOLUTION' THEN ARRAY['SOLUTION_APPROVED_SET','SOLUTION_COVERAGE'] END;
 IF (SELECT array_agg(item_key ORDER BY item_key) FROM plm.wfl_transition_gate_items WHERE stage_transition_id=root_id) IS DISTINCT FROM expected THEN
     RAISE EXCEPTION 'Workflow Gate item set incomplete'; END IF;
 IF EXISTS(SELECT 1 FROM plm.wfl_transition_gate_items g LEFT JOIN plm.wfl_checklist_items c ON c.workflow_id=g.workflow_id AND c.item_key=g.item_key
   WHERE g.stage_transition_id=root_id AND (g.required IS DISTINCT FROM c.required OR g.result IS DISTINCT FROM c.item_state
      OR g.evidence_policy_ref IS DISTINCT FROM c.evidence_policy_ref OR g.review_policy_ref IS DISTINCT FROM c.review_policy_ref)) THEN
     RAISE EXCEPTION 'Workflow Gate item facts mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM plm.wfl_transition_gate_items g WHERE g.stage_transition_id=root_id AND (
     NOT EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs r WHERE r.gate_item_id=g.gate_item_id AND r.ref_kind='EVIDENCE')
     OR NOT EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs r WHERE r.gate_item_id=g.gate_item_id AND r.ref_kind='REVIEW_ROUND')
     OR (g.result='WAIVED' AND NOT EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs r WHERE r.gate_item_id=g.gate_item_id AND r.ref_kind='APPROVED_EXCEPTION'))
     OR (g.result='PASS' AND EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs r WHERE r.gate_item_id=g.gate_item_id AND r.ref_kind='APPROVED_EXCEPTION')))) THEN
     RAISE EXCEPTION 'Workflow Gate basis incomplete'; END IF;
 IF EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs r JOIN plm.wfl_transition_gate_items g USING(gate_item_id,workflow_id,project_id)
   JOIN plm.evd_evidence_records e ON e.evidence_id=r.evidence_id WHERE g.stage_transition_id=root_id AND
   (r.ref_scope IS DISTINCT FROM e.scope OR r.ref_project_id IS DISTINCT FROM e.project_id OR r.observed_state IS DISTINCT FROM e.eligibility_state
    OR r.observed_lock_version IS DISTINCT FROM e.lock_version OR r.content_fingerprint IS DISTINCT FROM e.content_fingerprint)) THEN
     RAISE EXCEPTION 'Workflow Evidence facts changed before commit'; END IF;
 RETURN NULL;
END; $$;
"""

def upgrade() -> None:
    _make_tables(op.create_table)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}_guard BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_workflow_history()")
        op.execute(f"CREATE TRIGGER trg_{table}_truncate BEFORE TRUNCATE ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_workflow_history()")
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_{table}_complete AFTER INSERT ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.validate_workflow_history()")

def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Workflow history downgrade disabled")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.wfl_stage_transitions) OR EXISTS(SELECT 1 FROM plm.wfl_transition_gate_items) OR EXISTS(SELECT 1 FROM plm.wfl_transition_gate_refs)")):
        raise RuntimeError("Workflow success history exists; downgrade refused")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_workflow_history()")
    op.execute("DROP FUNCTION plm.guard_workflow_history()")
