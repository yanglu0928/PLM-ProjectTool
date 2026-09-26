"""Review owned metadata; never actual Subject/reviewer authorization."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from plm_assistant.modules.platform.infrastructure.orm import Base

def _make_tables(create):
    ident = postgresql.UUID(as_uuid=True)
    time = postgresql.TIMESTAMP(timezone=True, precision=6)
    zero = "'00000000-0000-0000-0000-000000000000'::uuid"
    def col(name, kind=sa.Text(), nullable=False, **kw):
        return sa.Column(name, kind, nullable=nullable, **kw)
    def pk(name):
        return sa.Column(name, ident, primary_key=True, server_default=sa.text("uuidv7()"))
    def check(name, expression):
        return sa.CheckConstraint(expression, name=name)
    def uq(name, *cols):
        return sa.UniqueConstraint(*cols, name=name)
    def fk(name, cols, target, refs, **kw):
        return sa.ForeignKeyConstraint(cols, ["plm."+target+"."+r for r in refs], name=name, ondelete="NO ACTION", **kw)
    def scope(tag):
        return [col("scope"), col("project_id", ident, nullable=True),
            sa.Column("scope_project_key", ident, sa.Computed("coalesce(project_id,"+zero+")", persisted=True), nullable=False),
            check("ck_"+tag+"__scope", "(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL AND project_id<>"+zero+")"),
            fk("fk_"+tag+"__project", ["project_id"], "prj_projects", ["project_id"])]
    def parent(tag, key, table):
        return fk("fk_"+tag+"__parent", [key,"scope","scope_project_key"], table, [key,"scope","scope_project_key"])
    def scoped_unique(tag, key):
        return uq("uq_"+tag+"__id_scope", key,"scope","scope_project_key")
    def nonzero(tag, *cols):
        return check("ck_"+tag+"__uuid", " AND ".join(c+"<>"+zero for c in cols))
    def stamp():
        return col("created_xid", sa.BigInteger(), server_default=sa.text("txid_current()"))
    def lock():
        return col("lock_version", sa.BigInteger(), server_default=sa.text("0"))
    review = create("rvw_reviews", pk("review_id"), *scope("rvw_reviews"),
        col("subject_type"), col("subject_id", ident), col("policy_code"),
        col("review_state", server_default=sa.text("'DRAFT'")), col("active_round_id", ident, nullable=True), lock(),
        col("created_by", ident), col("created_at", time, server_default=sa.text("statement_timestamp()")), stamp(),
        scoped_unique("rvw_reviews","review_id"),
        fk("fk_rvw_reviews__creator", ["created_by"], "auth_users", ["user_id"]),
        fk("fk_rvw_reviews__active_round", ["active_round_id","review_id","scope","scope_project_key"],
            "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"],
            deferrable=True, initially="DEFERRED", use_alter=True),
        check("ck_rvw_reviews__codes", "subject_type ~ '^[A-Z][A-Z0-9_-]{0,63}$' AND policy_code ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
        check("ck_rvw_reviews__state", "review_state IN ('DRAFT','IN_REVIEW','APPROVED','RETURNED','WITHDRAWN') AND lock_version>=0 AND ((review_state='IN_REVIEW' AND active_round_id IS NOT NULL) OR (review_state<>'IN_REVIEW' AND active_round_id IS NULL))"),
        nonzero("rvw_reviews","review_id","subject_id","created_by"),
        sa.Index("ix_rvw_reviews__subject", "scope","scope_project_key","subject_type","subject_id"), schema="plm")
    rounds = create("rvw_review_rounds", pk("review_round_id"), col("review_id", ident), *scope("rvw_rounds"),
        col("round_no", sa.Integer()), col("subject_version_id", ident), col("round_state"), lock(),
        col("started_by", ident), col("started_at", time), stamp(),
        col("changed_xid", sa.BigInteger(), server_default=sa.text("txid_current()")),
        parent("rvw_rounds","review_id","rvw_reviews"), scoped_unique("rvw_rounds","review_round_id"),
        uq("uq_rvw_rounds__id_review_scope","review_round_id","review_id","scope","scope_project_key"),
        uq("uq_rvw_rounds__number","review_id","round_no"),
        fk("fk_rvw_rounds__starter", ["started_by"], "auth_users", ["user_id"]),
        check("ck_rvw_rounds__state", "round_no>0 AND lock_version>=0 AND round_state IN ('PENDING','IN_REVIEW','APPROVED','RETURNED','WITHDRAWN') AND created_xid>0 AND changed_xid>0"),
        nonzero("rvw_rounds","review_round_id","subject_version_id","started_by"),
        sa.Index("uq_rvw_rounds__review_in_review","review_id", unique=True, postgresql_where=sa.text("round_state='IN_REVIEW'")), schema="plm")
    assignments = create("rvw_review_assignments", pk("assignment_id"), col("review_id", ident), col("review_round_id", ident),
        *scope("rvw_assignments"), col("reviewer_id", ident), col("assignment_state", server_default=sa.text("'PENDING'")),
        parent("rvw_assignments","review_round_id","rvw_review_rounds"),
        fk("fk_rvw_assignments__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        fk("fk_rvw_assignments__reviewer", ["reviewer_id"], "auth_users", ["user_id"]),
        uq("uq_rvw_assignments__round_reviewer","review_round_id","reviewer_id"),
        uq("uq_rvw_assignments__decision_parent","assignment_id","review_round_id","reviewer_id","scope","scope_project_key"),
        check("ck_rvw_assignments__state","assignment_state IN ('PENDING','DECIDED')"),
        nonzero("rvw_assignments","assignment_id","reviewer_id"), schema="plm")
    decisions = create("rvw_review_decisions", pk("decision_id"), col("review_id", ident), col("review_round_id", ident),
        *scope("rvw_decisions"), col("assignment_id", ident), col("reviewer_id", ident), col("decision"),
        col("comment", nullable=True), col("decided_at", time), col("trace_id", ident),
        col("round_after_version", sa.BigInteger()), stamp(),
        fk("fk_rvw_decisions__assignment", ["assignment_id","review_round_id","reviewer_id","scope","scope_project_key"],
            "rvw_review_assignments", ["assignment_id","review_round_id","reviewer_id","scope","scope_project_key"]),
        fk("fk_rvw_decisions__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        uq("uq_rvw_decisions__assignment","assignment_id"), uq("uq_rvw_decisions__round_version","review_round_id","round_after_version"),
        uq("uq_rvw_decisions__id_round","decision_id","review_round_id"),
        check("ck_rvw_decisions__decision","decision IN ('APPROVE','RETURN') AND round_after_version>0 AND created_xid>0 AND (decision<>'RETURN' OR (comment IS NOT NULL AND char_length(btrim(comment,chr(9)||chr(10)||chr(11)||chr(12)||chr(13)||chr(28)||chr(29)||chr(30)||chr(31)||chr(32)||chr(133)||chr(160)||chr(5760)||chr(8192)||chr(8193)||chr(8194)||chr(8195)||chr(8196)||chr(8197)||chr(8198)||chr(8199)||chr(8200)||chr(8201)||chr(8202)||chr(8232)||chr(8233)||chr(8239)||chr(8287)||chr(12288)))>0))"),
        nonzero("rvw_decisions","decision_id","trace_id"), schema="plm")
    snapshots = create("rvw_subject_snapshots", pk("snapshot_id"), col("review_id", ident), col("review_round_id", ident),
        *scope("rvw_snapshots"), col("subject_type"), col("subject_id", ident), col("subject_version_id", ident),
        col("content_fingerprint", sa.LargeBinary()), col("proof_schema_version", sa.Integer()),
        col("verified_at", time), stamp(),
        fk("fk_rvw_snapshots__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        scoped_unique("rvw_snapshots","snapshot_id"), uq("uq_rvw_snapshots__round","review_round_id"),
        check("ck_rvw_snapshots__proof","octet_length(content_fingerprint)=32 AND proof_schema_version=1 AND created_xid>0"),
        nonzero("rvw_snapshots","snapshot_id","subject_id","subject_version_id"), schema="plm")
    refs = create("rvw_subject_snapshot_refs", pk("snapshot_ref_id"), col("review_id", ident), col("review_round_id", ident),
        col("snapshot_id", ident), *scope("rvw_snapshot_refs"), col("ref_kind"), col("ref_id", ident), col("ref_scope"),
        col("ref_project_id", ident, nullable=True), col("observed_state"), col("observed_lock_version", sa.BigInteger()),
        col("content_fingerprint", sa.LargeBinary()), col("verified_at", time),
        sa.Column("evidence_id", ident, sa.Computed("CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END", persisted=True)),
        sa.Column("trace_link_id", ident, sa.Computed("CASE WHEN ref_kind='TRACE_LINK' THEN ref_id ELSE NULL END", persisted=True)),
        parent("rvw_snapshot_refs","snapshot_id","rvw_subject_snapshots"),
        fk("fk_rvw_snapshot_refs__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        fk("fk_rvw_snapshot_refs__evidence", ["evidence_id"], "evd_evidence_records", ["evidence_id"]),
        fk("fk_rvw_snapshot_refs__trace", ["trace_link_id"], "trc_links", ["trace_link_id"]),
        uq("uq_rvw_snapshot_refs__target","snapshot_id","ref_kind","ref_id"),
        check("ck_rvw_snapshot_refs__proof","observed_lock_version>=0 AND octet_length(content_fingerprint)=32 AND ((ref_kind='EVIDENCE' AND observed_state='ELIGIBLE') OR (ref_kind='TRACE_LINK' AND observed_state='ACTIVE'))"),
        check("ck_rvw_snapshot_refs__ref_scope","(ref_scope='PROJECT' AND scope='PROJECT' AND ref_project_id IS NOT NULL AND ref_project_id=project_id) OR (ref_scope='GLOBAL' AND ref_project_id IS NULL AND (scope='GLOBAL' OR ref_kind='EVIDENCE'))"),
        nonzero("rvw_snapshot_refs","snapshot_ref_id","ref_id"), schema="plm")
    locks = create("rvw_subject_locks", pk("subject_lock_id"), col("review_id", ident), col("review_round_id", ident),
        *scope("rvw_locks"), col("subject_type"), col("subject_id", ident), col("lock_state", server_default=sa.text("'ACTIVE'")),
        col("acquired_at", time), col("released_at", time, nullable=True),
        fk("fk_rvw_locks__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        uq("uq_rvw_locks__round","review_round_id"),
        check("ck_rvw_locks__state","(lock_state='ACTIVE' AND released_at IS NULL) OR (lock_state='RELEASED' AND released_at IS NOT NULL AND released_at>=acquired_at)"),
        nonzero("rvw_locks","subject_lock_id","subject_id"),
        sa.Index("uq_rvw_locks__active_subject","scope","scope_project_key","subject_type","subject_id", unique=True, postgresql_where=sa.text("lock_state='ACTIVE'")), schema="plm")
    events = create("rvw_round_events", pk("round_event_id"), col("review_id", ident), col("review_round_id", ident),
        *scope("rvw_events"), col("event_type"), col("actor_id", ident), col("trace_id", ident), col("occurred_at", time),
        col("before_lock_version", sa.BigInteger(), nullable=True), col("after_lock_version", sa.BigInteger()),
        col("result_state"), col("decision_id", ident, nullable=True),
        fk("fk_rvw_events__round_review", ["review_round_id","review_id","scope","scope_project_key"], "rvw_review_rounds", ["review_round_id","review_id","scope","scope_project_key"]),
        fk("fk_rvw_events__actor", ["actor_id"], "auth_users", ["user_id"]),
        fk("fk_rvw_events__decision", ["decision_id","review_round_id"], "rvw_review_decisions", ["decision_id","review_round_id"]),
        uq("uq_rvw_events__version_kind","review_round_id","after_lock_version","event_type"),
        check("ck_rvw_events__kind","(event_type='STARTED' AND before_lock_version IS NULL AND after_lock_version=0 AND result_state='IN_REVIEW' AND decision_id IS NULL) OR (before_lock_version IS NOT NULL AND before_lock_version>=0 AND after_lock_version=before_lock_version+1 AND ((event_type='DECISION_RECORDED' AND decision_id IS NOT NULL AND result_state IN ('IN_REVIEW','APPROVED','RETURNED')) OR (event_type='COMPLETED' AND decision_id IS NULL AND result_state IN ('APPROVED','RETURNED')) OR (event_type='WITHDRAWN' AND decision_id IS NULL AND result_state='WITHDRAWN')))"),
        nonzero("rvw_events","round_event_id","actor_id","trace_id"),
        sa.Index("uq_rvw_events__decision","decision_id", unique=True, postgresql_where=sa.text("decision_id IS NOT NULL")), schema="plm")
    return review, rounds, assignments, decisions, snapshots, refs, locks, events

_tables = _make_tables(lambda name, *args, **kwargs: sa.Table(name, Base.metadata, *args, **kwargs))

class ReviewRow(Base):
    __table__ = _tables[0]

class ReviewRoundRow(Base):
    __table__ = _tables[1]

class ReviewAssignmentRow(Base):
    __table__ = _tables[2]

class ReviewDecisionRow(Base):
    __table__ = _tables[3]

class ReviewSubjectSnapshotRow(Base):
    __table__ = _tables[4]

class ReviewSnapshotRefRow(Base):
    __table__ = _tables[5]

class ReviewSubjectLockRow(Base):
    __table__ = _tables[6]

class ReviewRoundEventRow(Base):
    __table__ = _tables[7]
