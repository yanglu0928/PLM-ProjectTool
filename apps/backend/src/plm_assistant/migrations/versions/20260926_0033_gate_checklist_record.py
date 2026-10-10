"""CR-WFL-004 fixed Gate record link; preserve legacy unlinked immutable history."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0033"
down_revision = "20260926_0032"
branch_labels = None
depends_on = None

_TABLE = "wfl_transition_gate_items"
_SHAPE = "(checklist_record_id IS NULL AND observed_item_version IS NULL AND record_fingerprint IS NULL) OR (checklist_record_id IS NOT NULL AND checklist_record_id<>'00000000-0000-0000-0000-000000000000'::uuid AND observed_item_version IS NOT NULL AND observed_item_version>0 AND record_fingerprint IS NOT NULL AND octet_length(record_fingerprint)=32)"
_GUARDS = """
CREATE FUNCTION plm.assert_gate_checklist_record(g plm.wfl_transition_gate_items) RETURNS void LANGUAGE plpgsql AS $$
DECLARE root plm.wfl_stage_transitions%ROWTYPE; r plm.wfl_checklist_records%ROWTYPE; c plm.wfl_checklist_items%ROWTYPE;
BEGIN
 IF g.checklist_record_id IS NULL OR g.observed_item_version IS NULL OR g.record_fingerprint IS NULL THEN
  RAISE EXCEPTION 'New Gate requires fixed Checklist record'; END IF;
 SELECT * INTO root FROM plm.wfl_stage_transitions WHERE stage_transition_id=g.stage_transition_id;
 IF NOT FOUND OR root.created_xid<>txid_current() THEN RAISE EXCEPTION 'Gate record parent sealed'; END IF;
 PERFORM 1 FROM plm.wfl_project_workflows WHERE workflow_id=g.workflow_id FOR UPDATE;
 SELECT * INTO r FROM plm.wfl_checklist_records WHERE record_id=g.checklist_record_id;
 IF NOT FOUND OR r.created_xid=txid_current() OR r.workflow_id IS DISTINCT FROM g.workflow_id
  OR r.project_id IS DISTINCT FROM g.project_id OR r.item_key IS DISTINCT FROM g.item_key
  OR r.stage_key IS DISTINCT FROM root.from_stage OR r.definition_version<>root.definition_version
  OR r.result IS DISTINCT FROM g.result OR r.result NOT IN ('PASS','WAIVED')
  OR r.after_item_version IS DISTINCT FROM g.observed_item_version
  OR r.content_fingerprint IS DISTINCT FROM g.record_fingerprint
  OR r.after_workflow_version>root.before_lock_version THEN
  RAISE EXCEPTION 'Gate fixed Checklist record mismatch'; END IF;
 SELECT * INTO c FROM plm.wfl_checklist_items WHERE workflow_id=g.workflow_id AND project_id=g.project_id AND item_key=g.item_key FOR SHARE;
 IF NOT FOUND OR c.lock_version IS DISTINCT FROM r.after_item_version OR c.item_state IS DISTINCT FROM r.result THEN
  RAISE EXCEPTION 'Gate Checklist record stale'; END IF;
 IF g.result='WAIVED' AND (g.waiver_reason IS DISTINCT FROM r.reason OR g.waiver_impact IS DISTINCT FROM r.impact) THEN
  RAISE EXCEPTION 'Gate waiver fixed details mismatch'; END IF;
END; $$;

CREATE FUNCTION plm.guard_gate_checklist_record() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM plm.assert_gate_checklist_record(NEW);
 RETURN NEW;
END; $$;

CREATE FUNCTION plm.validate_gate_checklist_record() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g plm.wfl_transition_gate_items%ROWTYPE;
BEGIN
 SELECT * INTO g FROM plm.wfl_transition_gate_items WHERE gate_item_id=NEW.gate_item_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Gate record item missing'; END IF;
 PERFORM plm.assert_gate_checklist_record(g);
 IF EXISTS(
  (SELECT ref_kind,ref_id,ref_scope,ref_project_id,content_fingerprint FROM plm.wfl_checklist_record_refs WHERE record_id=g.checklist_record_id
   EXCEPT SELECT ref_kind,ref_id,ref_scope,ref_project_id,content_fingerprint FROM plm.wfl_transition_gate_refs WHERE gate_item_id=g.gate_item_id)
  UNION ALL
  (SELECT ref_kind,ref_id,ref_scope,ref_project_id,content_fingerprint FROM plm.wfl_transition_gate_refs WHERE gate_item_id=g.gate_item_id
   EXCEPT SELECT ref_kind,ref_id,ref_scope,ref_project_id,content_fingerprint FROM plm.wfl_checklist_record_refs WHERE record_id=g.checklist_record_id)
 ) THEN RAISE EXCEPTION 'Gate fixed basis identity set mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM plm.wfl_checklist_record_refs r JOIN plm.wfl_transition_gate_refs f
   ON f.gate_item_id=g.gate_item_id AND f.ref_kind=r.ref_kind AND f.ref_id=r.ref_id
   WHERE r.record_id=g.checklist_record_id AND (f.observed_lock_version<r.observed_lock_version OR f.verified_at<r.verified_at)) THEN
  RAISE EXCEPTION 'Gate basis observation regressed'; END IF;
 RETURN NULL;
END; $$;
"""


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("checklist_record_id", postgresql.UUID(as_uuid=True), nullable=True), schema="plm")
    op.add_column(_TABLE, sa.Column("observed_item_version", sa.BigInteger(), nullable=True), schema="plm")
    op.add_column(_TABLE, sa.Column("record_fingerprint", sa.LargeBinary(), nullable=True), schema="plm")
    op.create_check_constraint("ck_wfl_gate_items__record_link", _TABLE, _SHAPE, schema="plm")
    op.create_foreign_key("fk_wfl_gate_items__record", _TABLE, "wfl_checklist_records",
        ["checklist_record_id", "workflow_id", "project_id", "item_key"],
        ["record_id", "workflow_id", "project_id", "item_key"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION")
    op.execute(_GUARDS)
    op.execute("CREATE TRIGGER trg_wfl_gate_record_guard BEFORE INSERT ON plm.wfl_transition_gate_items FOR EACH ROW EXECUTE FUNCTION plm.guard_gate_checklist_record()")
    for table in (_TABLE, "wfl_transition_gate_refs"):
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_{table}_record_complete AFTER INSERT ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.validate_gate_checklist_record()")


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Gate record downgrade disabled")
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM plm.wfl_transition_gate_items WHERE checklist_record_id IS NOT NULL)")):
        raise RuntimeError("Gate fixed record history exists; downgrade refused")
    op.execute("DROP TRIGGER trg_wfl_gate_record_guard ON plm.wfl_transition_gate_items")
    for table in (_TABLE, "wfl_transition_gate_refs"):
        op.execute(f"DROP TRIGGER trg_{table}_record_complete ON plm.{table}")
    op.execute("DROP FUNCTION plm.validate_gate_checklist_record()")
    op.execute("DROP FUNCTION plm.guard_gate_checklist_record()")
    op.execute("DROP FUNCTION plm.assert_gate_checklist_record(plm.wfl_transition_gate_items)")
    op.drop_constraint("fk_wfl_gate_items__record", _TABLE, schema="plm", type_="foreignkey")
    op.drop_constraint("ck_wfl_gate_items__record_link", _TABLE, schema="plm", type_="check")
    for column in ("record_fingerprint", "observed_item_version", "checklist_record_id"):
        op.drop_column(_TABLE, column, schema="plm")
