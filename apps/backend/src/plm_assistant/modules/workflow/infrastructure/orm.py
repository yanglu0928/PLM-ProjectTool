"""WFL-01 fixed definition instances; no Gate/permission proof implied."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # register dialect types

from plm_assistant.modules.platform.infrastructure.orm import Base

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

_tables = _make_tables(lambda name, *args, **kwargs: sa.Table(name, Base.metadata, *args, **kwargs))


class ProjectWorkflowRow(Base):
    __table__ = _tables[0]


class StageRow(Base):
    __table__ = _tables[1]


class StageChecklistRow(Base):
    __table__ = _tables[2]


class ChecklistItemRow(Base):
    __table__ = _tables[3]

