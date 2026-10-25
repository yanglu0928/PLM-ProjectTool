"""CR-RVW-001 owned Review structure; not actual Subject/customer authorization."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260926_0034"
down_revision = "20260926_0033"
branch_labels = None
depends_on = None

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

_TABLES = ("rvw_reviews","rvw_review_rounds","rvw_review_assignments","rvw_review_decisions","rvw_subject_snapshots","rvw_subject_snapshot_refs","rvw_subject_locks","rvw_round_events")
_GUARDS = """
CREATE FUNCTION plm.review_trace_fingerprint(t plm.trc_links) RETURNS bytea LANGUAGE sql IMMUTABLE AS $$
 SELECT sha256(convert_to(jsonb_build_array(t.trace_link_id,t.scope,t.project_id,t.source_owner_module,t.source_object_type,t.source_object_id,t.source_version_id,t.source_project_id,t.target_owner_module,t.target_object_type,t.target_object_id,t.target_version_id,t.target_project_id,t.relation_type)::text,'UTF8'));
$$;
CREATE FUNCTION plm.assert_review_snapshot_ref(r plm.rvw_subject_snapshot_refs) RETURNS void LANGUAGE plpgsql AS $$
DECLARE ev plm.evd_evidence_records%ROWTYPE; tr plm.trc_links%ROWTYPE;
BEGIN
 IF r.ref_kind='EVIDENCE' THEN
  SELECT * INTO ev FROM plm.evd_evidence_records WHERE evidence_id=r.ref_id FOR SHARE;
  IF NOT FOUND OR ev.scope IS DISTINCT FROM r.ref_scope OR ev.project_id IS DISTINCT FROM r.ref_project_id
   OR ev.eligibility_state IS DISTINCT FROM r.observed_state OR ev.lock_version IS DISTINCT FROM r.observed_lock_version
   OR ev.content_fingerprint IS DISTINCT FROM r.content_fingerprint THEN RAISE EXCEPTION 'Review Evidence facts mismatch'; END IF;
 ELSE
  SELECT * INTO tr FROM plm.trc_links WHERE trace_link_id=r.ref_id FOR SHARE;
  IF NOT FOUND OR tr.scope IS DISTINCT FROM r.ref_scope OR tr.project_id IS DISTINCT FROM r.ref_project_id
   OR tr.link_state IS DISTINCT FROM r.observed_state OR r.observed_lock_version<>0
   OR plm.review_trace_fingerprint(tr) IS DISTINCT FROM r.content_fingerprint THEN RAISE EXCEPTION 'Review Trace facts mismatch'; END IF;
 END IF;
END; $$;
CREATE FUNCTION plm.guard_review_persistence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rev plm.rvw_reviews%ROWTYPE; rr plm.rvw_review_rounds%ROWTYPE; a plm.rvw_review_assignments%ROWTYPE; d plm.rvw_review_decisions%ROWTYPE; snap plm.rvw_subject_snapshots%ROWTYPE;
BEGIN
 IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'Review history retained'; END IF;
 IF TG_TABLE_NAME='rvw_reviews' THEN
  IF TG_OP='INSERT' THEN
   IF NEW.review_state<>'DRAFT' OR NEW.lock_version<>0 OR NEW.active_round_id IS NOT NULL THEN RAISE EXCEPTION 'Review initial state invalid'; END IF;
   NEW.created_xid:=txid_current();
  ELSE
   IF (to_jsonb(NEW)-ARRAY['review_state','active_round_id','lock_version','scope_project_key']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['review_state','active_round_id','lock_version','scope_project_key'])
    OR NEW.lock_version<>OLD.lock_version+1 OR NEW.review_state='DRAFT'
    OR (OLD.review_state<>'IN_REVIEW' AND NEW.review_state<>'IN_REVIEW')
    OR (OLD.review_state='IN_REVIEW' AND NEW.review_state='IN_REVIEW' AND NEW.active_round_id IS DISTINCT FROM OLD.active_round_id)
    THEN RAISE EXCEPTION 'Review identity/state invalid'; END IF;
  END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO rev FROM plm.rvw_reviews WHERE review_id=NEW.review_id FOR UPDATE;
 IF NOT FOUND OR rev.scope IS DISTINCT FROM NEW.scope OR rev.project_id IS DISTINCT FROM NEW.project_id THEN RAISE EXCEPTION 'Review parent Scope mismatch'; END IF;
 IF TG_TABLE_NAME='rvw_review_rounds' THEN
  IF TG_OP='INSERT' THEN
   IF rev.review_state='IN_REVIEW' OR NEW.round_state<>'IN_REVIEW' OR NEW.lock_version<>0
    OR NEW.round_no<>(SELECT coalesce(max(round_no),0)+1 FROM plm.rvw_review_rounds WHERE review_id=NEW.review_id)
    OR EXISTS(SELECT 1 FROM plm.rvw_review_rounds WHERE review_id=NEW.review_id AND round_state='RETURNED' AND subject_version_id=NEW.subject_version_id)
    THEN RAISE EXCEPTION 'Review Round initial/version invalid'; END IF;
   NEW.created_xid:=txid_current(); NEW.changed_xid:=txid_current();
  ELSE
   IF (to_jsonb(NEW)-ARRAY['round_state','lock_version','changed_xid','scope_project_key']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['round_state','lock_version','changed_xid','scope_project_key'])
    OR OLD.round_state<>'IN_REVIEW' OR NEW.round_state NOT IN ('IN_REVIEW','APPROVED','RETURNED','WITHDRAWN') OR NEW.lock_version<>OLD.lock_version+1
    THEN RAISE EXCEPTION 'Review Round sealed or state invalid'; END IF;
   NEW.changed_xid:=txid_current();
  END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO rr FROM plm.rvw_review_rounds WHERE review_round_id=NEW.review_round_id FOR UPDATE;
 IF NOT FOUND OR rr.review_id IS DISTINCT FROM NEW.review_id OR rr.scope IS DISTINCT FROM NEW.scope OR rr.project_id IS DISTINCT FROM NEW.project_id THEN RAISE EXCEPTION 'Review Round parent mismatch'; END IF;
 IF TG_TABLE_NAME IN ('rvw_review_decisions','rvw_subject_snapshots','rvw_subject_snapshot_refs','rvw_round_events') AND TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Review immutable record'; END IF;
 IF TG_TABLE_NAME='rvw_review_assignments' THEN
  IF TG_OP='INSERT' THEN
   IF rr.created_xid<>txid_current() OR NEW.assignment_state<>'PENDING' THEN RAISE EXCEPTION 'Review reviewer set sealed'; END IF;
  ELSE
   IF (to_jsonb(NEW)-ARRAY['assignment_state','scope_project_key']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['assignment_state','scope_project_key'])
    OR OLD.assignment_state<>'PENDING' OR NEW.assignment_state<>'DECIDED' OR rr.round_state<>'IN_REVIEW' THEN RAISE EXCEPTION 'Review Assignment state invalid'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='rvw_review_decisions' THEN
  SELECT * INTO a FROM plm.rvw_review_assignments WHERE assignment_id=NEW.assignment_id FOR UPDATE;
  IF NOT FOUND OR a.review_round_id IS DISTINCT FROM rr.review_round_id OR a.reviewer_id IS DISTINCT FROM NEW.reviewer_id
   OR a.assignment_state<>'PENDING' OR rr.round_state<>'IN_REVIEW' OR NEW.decided_at<rr.started_at THEN RAISE EXCEPTION 'Review Decision current Assignment invalid'; END IF;
  NEW.round_after_version:=rr.lock_version+1; NEW.created_xid:=txid_current();
 ELSIF TG_TABLE_NAME='rvw_subject_snapshots' THEN
  IF rr.created_xid<>txid_current() OR NEW.subject_type IS DISTINCT FROM rev.subject_type OR NEW.subject_id IS DISTINCT FROM rev.subject_id OR NEW.subject_version_id IS DISTINCT FROM rr.subject_version_id THEN RAISE EXCEPTION 'Review Subject snapshot sealed/mismatch'; END IF;
  NEW.created_xid:=txid_current();
 ELSIF TG_TABLE_NAME='rvw_subject_snapshot_refs' THEN
  SELECT * INTO snap FROM plm.rvw_subject_snapshots WHERE snapshot_id=NEW.snapshot_id;
  IF NOT FOUND OR snap.created_xid<>txid_current() OR snap.review_id IS DISTINCT FROM NEW.review_id OR snap.review_round_id IS DISTINCT FROM rr.review_round_id THEN RAISE EXCEPTION 'Review Subject refs sealed/mismatch'; END IF;
  PERFORM plm.assert_review_snapshot_ref(NEW);
 ELSIF TG_TABLE_NAME='rvw_subject_locks' THEN
  IF TG_OP='INSERT' THEN
   IF rr.created_xid<>txid_current() OR NEW.lock_state<>'ACTIVE' OR NEW.subject_type IS DISTINCT FROM rev.subject_type OR NEW.subject_id IS DISTINCT FROM rev.subject_id THEN RAISE EXCEPTION 'Review Subject lock initial invalid'; END IF;
  ELSE
   IF (to_jsonb(NEW)-ARRAY['lock_state','released_at','scope_project_key']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['lock_state','released_at','scope_project_key'])
    OR OLD.lock_state<>'ACTIVE' OR NEW.lock_state<>'RELEASED' OR rr.round_state NOT IN ('APPROVED','RETURNED','WITHDRAWN') OR rr.changed_xid<>txid_current() THEN RAISE EXCEPTION 'Review Subject lock release invalid'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='rvw_round_events' THEN
  IF rr.changed_xid<>txid_current() OR rr.lock_version IS DISTINCT FROM NEW.after_lock_version OR rr.round_state IS DISTINCT FROM NEW.result_state OR NEW.occurred_at<rr.started_at THEN RAISE EXCEPTION 'Review event sealed/current facts mismatch'; END IF;
  IF NEW.event_type='STARTED' AND (rr.created_xid<>txid_current() OR NEW.actor_id IS DISTINCT FROM rr.started_by) THEN RAISE EXCEPTION 'Review start event mismatch'; END IF;
  IF NEW.event_type='DECISION_RECORDED' THEN
   SELECT * INTO d FROM plm.rvw_review_decisions WHERE decision_id=NEW.decision_id;
   IF NOT FOUND OR d.created_xid<>txid_current() OR d.reviewer_id IS DISTINCT FROM NEW.actor_id OR d.round_after_version<>NEW.after_lock_version OR NEW.occurred_at<d.decided_at THEN RAISE EXCEPTION 'Review decision event mismatch'; END IF;
  END IF;
  IF NEW.event_type IN ('COMPLETED','WITHDRAWN') AND EXISTS(SELECT 1 FROM plm.rvw_review_decisions WHERE review_round_id=rr.review_round_id AND decided_at>NEW.occurred_at) THEN RAISE EXCEPTION 'Review terminal event chronology invalid'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE FUNCTION plm.validate_review_persistence() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rev plm.rvw_reviews%ROWTYPE; rr plm.rvw_review_rounds%ROWTYPE; ac bigint; dc bigint; expected text; active_id uuid; ref plm.rvw_subject_snapshot_refs%ROWTYPE;
BEGIN
 SELECT * INTO rev FROM plm.rvw_reviews WHERE review_id=NEW.review_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Review root missing'; END IF;
 IF rev.lock_version<>(SELECT count(*)+coalesce(sum(lock_version),0) FROM plm.rvw_review_rounds WHERE review_id=rev.review_id) THEN RAISE EXCEPTION 'Review version/event atomicity invalid'; END IF;
 IF EXISTS(SELECT 1 FROM (SELECT round_no,row_number() OVER(ORDER BY round_no) n FROM plm.rvw_review_rounds WHERE review_id=rev.review_id) q WHERE round_no<>n) THEN RAISE EXCEPTION 'Review round sequence incomplete'; END IF;
 FOR rr IN SELECT * FROM plm.rvw_review_rounds WHERE review_id=rev.review_id ORDER BY round_no LOOP
  SELECT count(*) INTO ac FROM plm.rvw_review_assignments WHERE review_round_id=rr.review_round_id;
  SELECT count(*) INTO dc FROM plm.rvw_review_decisions WHERE review_round_id=rr.review_round_id;
  IF ac<1 OR (SELECT count(*) FROM plm.rvw_subject_snapshots WHERE review_round_id=rr.review_round_id)<>1
   OR (SELECT count(*) FROM plm.rvw_subject_locks WHERE review_round_id=rr.review_round_id)<>1 THEN RAISE EXCEPTION 'Review Round start incomplete'; END IF;
  IF EXISTS(SELECT 1 FROM plm.rvw_review_assignments a WHERE a.review_round_id=rr.review_round_id AND (a.assignment_state='DECIDED') IS DISTINCT FROM EXISTS(SELECT 1 FROM plm.rvw_review_decisions d WHERE d.assignment_id=a.assignment_id)) THEN RAISE EXCEPTION 'Review Assignment/Decision atomicity invalid'; END IF;
  expected:=(CASE WHEN dc<ac THEN 'IN_REVIEW' WHEN EXISTS(SELECT 1 FROM plm.rvw_review_decisions WHERE review_round_id=rr.review_round_id AND decision='RETURN') THEN 'RETURNED' ELSE 'APPROVED' END);
  IF (rr.round_state='WITHDRAWN' AND dc>=ac) OR (rr.round_state<>'WITHDRAWN' AND rr.round_state IS DISTINCT FROM expected)
   OR rr.lock_version<>dc+(CASE WHEN rr.round_state='WITHDRAWN' THEN 1 ELSE 0 END) THEN RAISE EXCEPTION 'Review complete-set state invalid'; END IF;
  IF EXISTS(SELECT 1 FROM plm.rvw_subject_locks WHERE review_round_id=rr.review_round_id AND lock_state IS DISTINCT FROM (CASE WHEN rr.round_state='IN_REVIEW' THEN 'ACTIVE' ELSE 'RELEASED' END)) THEN RAISE EXCEPTION 'Review Subject lock atomicity invalid'; END IF;
  IF (SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=rr.review_round_id AND event_type='STARTED')<>1
   OR (SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=rr.review_round_id AND event_type='DECISION_RECORDED')<>dc
   OR (SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=rr.review_round_id AND event_type='COMPLETED')<>(CASE WHEN rr.round_state IN ('APPROVED','RETURNED') THEN 1 ELSE 0 END)
   OR (SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=rr.review_round_id AND event_type='WITHDRAWN')<>(CASE WHEN rr.round_state='WITHDRAWN' THEN 1 ELSE 0 END) THEN RAISE EXCEPTION 'Review events incomplete'; END IF;
  IF EXISTS(SELECT 1 FROM plm.rvw_review_decisions d WHERE d.review_round_id=rr.review_round_id AND NOT EXISTS(SELECT 1 FROM plm.rvw_round_events e WHERE e.decision_id=d.decision_id AND e.event_type='DECISION_RECORDED' AND e.after_lock_version=d.round_after_version)) THEN RAISE EXCEPTION 'Review decision event missing'; END IF;
  IF rr.created_xid=txid_current() THEN
   FOR ref IN SELECT * FROM plm.rvw_subject_snapshot_refs WHERE review_round_id=rr.review_round_id LOOP PERFORM plm.assert_review_snapshot_ref(ref); END LOOP;
  END IF;
 END LOOP;
 SELECT review_round_id INTO active_id FROM plm.rvw_review_rounds WHERE review_id=rev.review_id AND round_state='IN_REVIEW';
 IF rev.active_round_id IS DISTINCT FROM active_id OR (active_id IS NOT NULL AND rev.review_state<>'IN_REVIEW')
  OR (active_id IS NULL AND rev.review_state IS DISTINCT FROM coalesce((SELECT round_state FROM plm.rvw_review_rounds WHERE review_id=rev.review_id ORDER BY round_no DESC LIMIT 1),'DRAFT')) THEN RAISE EXCEPTION 'Review active/status projection invalid'; END IF;
 RETURN NULL;
END; $$;
"""

def upgrade() -> None:
    _make_tables(op.create_table)
    op.create_foreign_key("fk_rvw_reviews__active_round","rvw_reviews","rvw_review_rounds",
        ["active_round_id","review_id","scope","scope_project_key"],["review_round_id","review_id","scope","scope_project_key"],
        source_schema="plm",referent_schema="plm",ondelete="NO ACTION",deferrable=True,initially="DEFERRED")
    op.execute(_GUARDS)
    for table in _TABLES:
        op.execute(f"CREATE TRIGGER trg_{table}_guard BEFORE INSERT OR UPDATE OR DELETE ON plm.{table} FOR EACH ROW EXECUTE FUNCTION plm.guard_review_persistence()")
        op.execute(f"CREATE TRIGGER trg_{table}_truncate BEFORE TRUNCATE ON plm.{table} FOR EACH STATEMENT EXECUTE FUNCTION plm.guard_review_persistence()")
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_{table}_complete AFTER INSERT OR UPDATE ON plm.{table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION plm.validate_review_persistence()")

def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline Review downgrade disabled")
    if op.get_bind().scalar(sa.text("SELECT "+" OR ".join("EXISTS(SELECT 1 FROM plm."+table+")" for table in _TABLES))):
        raise RuntimeError("Review history exists; downgrade refused")
    for table in _TABLES:
        for suffix in ("guard","truncate","complete"):
            op.execute(f"DROP TRIGGER trg_{table}_{suffix} ON plm.{table}")
    op.execute("DROP FUNCTION plm.validate_review_persistence()")
    op.execute("DROP FUNCTION plm.guard_review_persistence()")
    op.execute("DROP FUNCTION plm.assert_review_snapshot_ref(plm.rvw_subject_snapshot_refs)")
    op.execute("DROP FUNCTION plm.review_trace_fingerprint(plm.trc_links)")
    op.drop_constraint("fk_rvw_reviews__active_round","rvw_reviews",schema="plm",type_="foreignkey")
    for table in reversed(_TABLES):
        op.drop_table(table,schema="plm")
