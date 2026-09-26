"""CR-WFL-003 append-only history metadata; no runtime Gate proof."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from plm_assistant.modules.platform.infrastructure.orm import Base

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

_tables = _make_tables(lambda name, *args, **kwargs: sa.Table(name, Base.metadata, *args, **kwargs))

class StageTransitionRow(Base):
    __table__ = _tables[0]

class TransitionGateItemRow(Base):
    __table__ = _tables[1]

class TransitionGateRefRow(Base):
    __table__ = _tables[2]
