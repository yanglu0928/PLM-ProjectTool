"""WFL-01 fixed definition instance structure. Runtime Gate remains separate."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0030"
down_revision = "20260926_0029"
branch_labels = None
depends_on = None

def _make_tables(create):
    ident = sa.dialects.postgresql.UUID(as_uuid=True)
    time = sa.dialects.postgresql.TIMESTAMP(timezone=True, precision=6)
    def pk(name):
        return sa.Column(name, ident, primary_key=True, server_default=sa.text("uuidv7()"))
    def key(name):
        return sa.Column(name, sa.Text(), nullable=False)
    def lock():
        return sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
    def state(name, value):
        return sa.Column(name, sa.Text(), nullable=False, server_default=sa.text("'" + value + "'"))
    def unique(name, *cols):
        return sa.UniqueConstraint(*cols, name=name)
    def check(name, expression):
        return sa.CheckConstraint(expression, name=name)
    def fk(name, cols, targets):
        return sa.ForeignKeyConstraint(cols, targets, name=name, ondelete="NO ACTION")
    def parent(parent_id, parent_table):
        return fk("fk_" + parent_table + "__child_" + parent_id,
                  [parent_id, "workflow_id", "project_id"],
                  ["plm." + parent_table + "." + c for c in (parent_id, "workflow_id", "project_id")])
    workflow = create(
        "wfl_project_workflows", pk("workflow_id"),
        sa.Column("project_id", ident, nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        state("workflow_state", "NOT_STARTED"),
        sa.Column("current_stage_key", sa.Text()),
        sa.Column("definition_fingerprint", sa.LargeBinary(), nullable=False),
        lock(), sa.Column("created_by", ident, nullable=False),
        sa.Column("created_at", time, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_at", time, nullable=False, server_default=sa.text("statement_timestamp()")),
        unique("uq_wfl_workflows__project", "project_id"),
        unique("uq_wfl_workflows__id_project", "workflow_id", "project_id"),
        fk("fk_wfl_workflows__project", ["project_id"], ["plm.prj_projects.project_id"]),
        fk("fk_wfl_workflows__creator", ["created_by"], ["plm.auth_users.user_id"]),
        check("ck_wfl_workflows__version", "workflow_version=1"),
        check("ck_wfl_workflows__state", "workflow_state IN ('NOT_STARTED','ACTIVE','COMPLETED')"),
        check("ck_wfl_workflows__lock", "lock_version>=0"),
        check("ck_wfl_workflows__fingerprint", "definition_fingerprint=decode('4bcda512e4c0d26a9766bdb41d9086a73a6d187db61d319ff94a1e929c3802a9','hex')"),
        schema="plm",
    )
    stages = create(
        "wfl_stages", pk("stage_id"),
        sa.Column("workflow_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        key("stage_key"), sa.Column("stage_order", sa.Integer(), nullable=False),
        key("gate_policy_ref"), state("stage_state", "NOT_STARTED"),
        fk("fk_wfl_stages__workflow", ["workflow_id", "project_id"],
           ["plm.wfl_project_workflows.workflow_id", "plm.wfl_project_workflows.project_id"]),
        unique("uq_wfl_stages__key", "workflow_id", "stage_key"),
        unique("uq_wfl_stages__order", "workflow_id", "stage_order"),
        unique("uq_wfl_stages__id_workflow_project", "stage_id", "workflow_id", "project_id"),
        check("ck_wfl_stages__order", "stage_order>0"),
        check("ck_wfl_stages__state", "stage_state IN ('NOT_STARTED','ACTIVE','BLOCKED','COMPLETED')"),
        check("ck_wfl_stages__key", "stage_key ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
        check("ck_wfl_stages__policy", "gate_policy_ref ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
        schema="plm",
    )
    checklists = create(
        "wfl_stage_checklists", pk("stage_checklist_id"),
        sa.Column("stage_id", ident, nullable=False),
        sa.Column("workflow_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        parent("stage_id", "wfl_stages"),
        unique("uq_wfl_checklists__stage", "stage_id"),
        unique("uq_wfl_checklists__id_workflow_project", "stage_checklist_id", "workflow_id", "project_id"),
        schema="plm",
    )
    items = create(
        "wfl_checklist_items", pk("checklist_item_id"),
        sa.Column("stage_checklist_id", ident, nullable=False),
        sa.Column("workflow_id", ident, nullable=False), sa.Column("project_id", ident, nullable=False),
        key("item_key"), sa.Column("required", sa.Boolean(), nullable=False),
        key("evidence_policy_ref"), key("review_policy_ref"),
        state("item_state", "PENDING"), lock(),
        parent("stage_checklist_id", "wfl_stage_checklists"),
        unique("uq_wfl_items__key", "workflow_id", "item_key"),
        check("ck_wfl_items__state", "item_state IN ('PENDING','PASS','FAIL','WAIVED')"),
        check("ck_wfl_items__lock", "lock_version>=0"),
        check("ck_wfl_items__keys", "item_key ~ '^[A-Z][A-Z0-9_]{0,63}$' AND evidence_policy_ref ~ '^[A-Z][A-Z0-9_]{0,63}$' AND review_policy_ref ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
        schema="plm",
    )
    return workflow, stages, checklists, items

_TABLES = ("wfl_project_workflows", "wfl_stages", "wfl_stage_checklists", "wfl_checklist_items")
_GUARDS = """
CREATE FUNCTION plm.guard_workflow_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE allowed text[]; old_order integer; new_order integer;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Workflow history retained'; END IF;
 IF TG_OP='INSERT' THEN
   IF TG_TABLE_NAME='wfl_project_workflows' THEN
    IF NEW.workflow_state<>'NOT_STARTED' OR NEW.current_stage_key IS NOT NULL OR NEW.lock_version<>0 THEN
     RAISE EXCEPTION 'Workflow initial state invalid'; END IF;
   ELSIF TG_TABLE_NAME='wfl_stages' THEN
    IF NEW.stage_state<>'NOT_STARTED' THEN
     RAISE EXCEPTION 'Stage initial state invalid'; END IF;
   ELSIF TG_TABLE_NAME='wfl_checklist_items' THEN
    IF NEW.item_state<>'PENDING' OR NEW.lock_version<>0 THEN
     RAISE EXCEPTION 'Checklist initial state invalid'; END IF;
   END IF;
   RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='wfl_project_workflows' THEN
   allowed:=ARRAY['workflow_state','current_stage_key','lock_version','updated_at'];
   IF NEW.lock_version<>OLD.lock_version+1 OR NEW.updated_at<OLD.updated_at
      OR OLD.workflow_state='COMPLETED' OR NEW.workflow_state='NOT_STARTED' THEN
     RAISE EXCEPTION 'Workflow update invalid';
   END IF;
   SELECT stage_order INTO new_order FROM plm.wfl_stages WHERE workflow_id=OLD.workflow_id AND stage_key=NEW.current_stage_key;
   IF OLD.workflow_state='NOT_STARTED' THEN
     IF NEW.workflow_state<>'ACTIVE' OR new_order IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'Workflow start invalid'; END IF;
   ELSE
     SELECT stage_order INTO old_order FROM plm.wfl_stages WHERE workflow_id=OLD.workflow_id AND stage_key=OLD.current_stage_key;
     IF new_order IS NULL OR old_order IS NULL OR new_order NOT IN (old_order,old_order+1) THEN RAISE EXCEPTION 'Workflow jump invalid'; END IF;
     IF NEW.workflow_state='COMPLETED' AND old_order<>6 THEN RAISE EXCEPTION 'Workflow premature completion'; END IF;
   END IF;
 ELSIF TG_TABLE_NAME='wfl_stages' THEN
   allowed:=ARRAY['stage_state'];
   IF NOT ((OLD.stage_state='NOT_STARTED' AND NEW.stage_state='ACTIVE')
        OR (OLD.stage_state='ACTIVE' AND NEW.stage_state IN ('BLOCKED','COMPLETED'))
        OR (OLD.stage_state='BLOCKED' AND NEW.stage_state='ACTIVE')) THEN
     RAISE EXCEPTION 'Stage transition invalid';
   END IF;
 ELSIF TG_TABLE_NAME='wfl_checklist_items' THEN
   allowed:=ARRAY['item_state','lock_version'];
   IF NEW.lock_version<>OLD.lock_version+1 OR NEW.item_state='PENDING' THEN RAISE EXCEPTION 'Checklist update invalid'; END IF;
 ELSE
   RAISE EXCEPTION 'Checklist definition immutable';
 END IF;
 IF (to_jsonb(NEW)-allowed) IS DISTINCT FROM (to_jsonb(OLD)-allowed) THEN
   RAISE EXCEPTION 'Workflow definition immutable';
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION plm.validate_workflow_instance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE w plm.wfl_project_workflows%ROWTYPE; current_order integer; expected_key text; expected_items text[]; i integer;
keys constant text[]:=ARRAY['HANDOVER','SURVEY','REQUIREMENT','PROTOTYPE','SOLUTION','PLAN'];
BEGIN
 SELECT * INTO w FROM plm.wfl_project_workflows WHERE workflow_id=NEW.workflow_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Workflow missing'; END IF;
 IF (SELECT count(*) FROM plm.wfl_stages WHERE workflow_id=w.workflow_id)<>6
 OR (SELECT count(*) FROM plm.wfl_stage_checklists WHERE workflow_id=w.workflow_id)<>6
 OR (SELECT count(*) FROM plm.wfl_checklist_items WHERE workflow_id=w.workflow_id)<>12 THEN
   RAISE EXCEPTION 'Workflow definition incomplete';
 END IF;
 FOR i IN 1..6 LOOP
   expected_key:=keys[i];
   expected_items:=CASE i
     WHEN 1 THEN ARRAY['HANDOVER_BASELINE','HANDOVER_ISSUES']
     WHEN 2 THEN ARRAY['SURVEY_ACTUAL_SOURCES','SURVEY_CONCLUSION']
     WHEN 3 THEN ARRAY['REQUIREMENT_ACCEPTANCE','REQUIREMENT_FORMAL_VERSIONS']
     WHEN 4 THEN ARRAY['PROTOTYPE_COVERAGE','PROTOTYPE_SCOPE_DECISIONS']
     WHEN 5 THEN ARRAY['SOLUTION_APPROVED_SET','SOLUTION_COVERAGE']
     WHEN 6 THEN ARRAY['PLAN_APPROVED_BASELINE','PLAN_WBS_VALIDATION'] END;
   IF NOT EXISTS (SELECT 1 FROM plm.wfl_stages s WHERE s.workflow_id=w.workflow_id AND s.project_id=w.project_id
          AND s.stage_key=expected_key AND s.stage_order=i AND s.gate_policy_ref='GATE_'||expected_key||'_V1') THEN
      RAISE EXCEPTION 'Workflow stage definition invalid';
   END IF;
   IF (SELECT array_agg(t.item_key ORDER BY t.item_key)
         FROM plm.wfl_checklist_items t
         JOIN plm.wfl_stage_checklists c USING(stage_checklist_id,workflow_id,project_id)
         JOIN plm.wfl_stages s USING(stage_id,workflow_id,project_id)
         WHERE s.workflow_id=w.workflow_id AND s.stage_key=expected_key
         AND t.required AND t.evidence_policy_ref='EVIDENCE_FIXED_PROJECT_V1'
         AND t.review_policy_ref='REVIEW_'||expected_key||'_V1') IS DISTINCT FROM expected_items THEN
      RAISE EXCEPTION 'Workflow item definition invalid';
   END IF;
 END LOOP;
 SELECT stage_order INTO current_order FROM plm.wfl_stages WHERE workflow_id=w.workflow_id AND stage_key=w.current_stage_key;
 IF w.workflow_state='NOT_STARTED' THEN
   IF w.current_stage_key IS NOT NULL OR EXISTS(SELECT 1 FROM plm.wfl_stages WHERE workflow_id=w.workflow_id AND stage_state<>'NOT_STARTED')
      OR EXISTS(SELECT 1 FROM plm.wfl_checklist_items WHERE workflow_id=w.workflow_id AND item_state<>'PENDING') THEN
     RAISE EXCEPTION 'Workflow initial structure invalid';
   END IF;
 ELSIF w.workflow_state='ACTIVE' THEN
   IF current_order IS NULL OR EXISTS(SELECT 1 FROM plm.wfl_stages WHERE workflow_id=w.workflow_id AND
       ((stage_order<current_order AND stage_state<>'COMPLETED')
        OR (stage_order=current_order AND stage_state NOT IN ('ACTIVE','BLOCKED'))
        OR (stage_order>current_order AND stage_state<>'NOT_STARTED'))) THEN
     RAISE EXCEPTION 'Workflow current stage structure invalid';
   END IF;
 ELSE
   IF current_order IS DISTINCT FROM 6 OR EXISTS(SELECT 1 FROM plm.wfl_stages WHERE workflow_id=w.workflow_id AND stage_state<>'COMPLETED') THEN
     RAISE EXCEPTION 'Workflow completion structure invalid';
   END IF;
 END IF;
 RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    _make_tables(op.create_table)
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}_guard BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_workflow_row()")
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_{table}_complete AFTER INSERT OR UPDATE ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.validate_workflow_instance()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Workflow downgrade disabled")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.wfl_project_workflows)")):
        raise RuntimeError("Workflow history exists; downgrade refused")
    for table in reversed(_TABLES):
        op.drop_table(table, schema="plm")
    op.execute("DROP FUNCTION plm.validate_workflow_instance()")
    op.execute("DROP FUNCTION plm.guard_workflow_row()")
