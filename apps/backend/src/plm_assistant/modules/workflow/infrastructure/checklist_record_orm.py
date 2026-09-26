"""CR-WFL-004 record-chain metadata; not actual Owner or Gate approval."""
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

_tables = _make_tables(lambda name, *args, **kwargs: sa.Table(name, Base.metadata, *args, **kwargs))

class ChecklistRecordRow(Base):
    __table__ = _tables[0]

class ChecklistRecordRefRow(Base):
    __table__ = _tables[1]
