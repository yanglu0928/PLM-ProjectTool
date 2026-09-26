"""Disposable Review structure proof; Subject/reviewer资格/批准 not verified."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

spec = spec_from_file_location("_review_fixture", Path(__file__).resolve().parents[1] / "wfl-01-a05-p03-checklist-schema" / "verify.py")
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)
connect, insert = fixture.connect, fixture.insert
TABLES = ("rvw_reviews", "rvw_review_rounds", "rvw_review_assignments", "rvw_review_decisions",
          "rvw_subject_snapshots", "rvw_subject_snapshot_refs", "rvw_subject_locks", "rvw_round_events")
HASH = b"r"*32


def snapshot(db):
    return tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table))).fetchall()
                 for table in TABLES+("evd_evidence_records", "trc_links"))


def reject(db, action):
    before = snapshot(db)
    try:
        with db.transaction():
            action()
    except psycopg.Error as exc:
        assert exc.sqlstate in ("P0001", "23514", "23503", "23505", "23502"), (exc.sqlstate, exc.diag.message_primary)
        assert snapshot(db) == before
        return
    raise AssertionError("invalid Review structure accepted")


def review(db, actor, project, subject=None):
    return insert(db, TABLES[0], dict(scope="GLOBAL" if project is None else "PROJECT", project_id=project,
        subject_type="CAP-02" if project is None else "HND-02", subject_id=subject or uuid.uuid4(),
        policy_code="SYNTHETIC_ALL_V1", created_by=actor), "review_id")


def event(db, scope, project, review_id, round_id, actor, kind, version, state, decision=None):
    return insert(db, TABLES[7], dict(review_id=review_id, review_round_id=round_id, scope=scope, project_id=project,
        event_type=kind, actor_id=actor, trace_id=uuid.uuid4(), occurred_at=datetime.now(timezone.utc),
        before_lock_version=None if kind == "STARTED" else version-1, after_lock_version=version,
        result_state=state, decision_id=decision), "round_event_id")


def start(db, review_id, actor, reviewers, evidence=None, trace=None, *, version=None,
          omit=None, changes=None, ref_changes=None):
    scope, project, subject_type, subject = db.execute("SELECT scope,project_id,subject_type,subject_id FROM plm.rvw_reviews WHERE review_id=%s FOR UPDATE", (review_id,)).fetchone()
    number = db.execute("SELECT coalesce(max(round_no),0)+1 FROM plm.rvw_review_rounds WHERE review_id=%s", (review_id,)).fetchone()[0]
    fixed_version = version or uuid.uuid4()
    parent = dict(review_id=review_id, scope=scope, project_id=project)
    values = dict(parent, round_no=number, subject_version_id=fixed_version, round_state="IN_REVIEW",
                  started_by=actor, started_at=datetime.now(timezone.utc), created_xid=1, changed_xid=1)
    values.update(changes or {})
    round_id = insert(db, TABLES[1], values, "review_round_id")
    child = dict(parent, review_round_id=round_id)
    assignments = []
    if omit != "assignments":
        for user in reviewers:
            assignments.append(insert(db, TABLES[2], dict(child, reviewer_id=user), "assignment_id"))
    if omit != "snapshot":
        snap = insert(db, TABLES[4], dict(child, subject_type=subject_type, subject_id=subject,
            subject_version_id=fixed_version, content_fingerprint=HASH, proof_schema_version=1,
            verified_at=datetime.now(timezone.utc), created_xid=1), "snapshot_id")
        for kind, identity in (("EVIDENCE", evidence), ("TRACE_LINK", trace)):
            if identity is None:
                continue
            if kind == "EVIDENCE":
                s, p, state, v, fp = db.execute("SELECT scope,project_id,eligibility_state,lock_version,content_fingerprint FROM plm.evd_evidence_records WHERE evidence_id=%s", (identity,)).fetchone()
            else:
                s, p, state, fp = db.execute("SELECT scope,project_id,link_state,plm.review_trace_fingerprint(t) FROM plm.trc_links t WHERE trace_link_id=%s", (identity,)).fetchone()
                v = 0
            values = dict(child, snapshot_id=snap, ref_kind=kind, ref_id=identity, ref_scope=s,
                ref_project_id=p, observed_state=state, observed_lock_version=v,
                content_fingerprint=fp, verified_at=datetime.now(timezone.utc))
            values.update(ref_changes or {})
            insert(db, TABLES[5], values, "snapshot_ref_id")
    if omit != "lock":
        insert(db, TABLES[6], dict(child, subject_type=subject_type, subject_id=subject,
                                 acquired_at=datetime.now(timezone.utc)), "subject_lock_id")
    if omit != "review":
        db.execute("UPDATE plm.rvw_reviews SET review_state='IN_REVIEW',active_round_id=%s,lock_version=lock_version+1 WHERE review_id=%s", (round_id, review_id))
    if omit != "event":
        event(db, scope, project, review_id, round_id, actor, "STARTED", 0, "IN_REVIEW")
    return round_id, tuple(assignments), fixed_version


def decide(db, round_id, reviewer, choice="APPROVE", *, comment=None, omit=None, force_state=None):
    review_id = db.execute("SELECT review_id FROM plm.rvw_review_rounds WHERE review_round_id=%s", (round_id,)).fetchone()[0]
    db.execute("SELECT 1 FROM plm.rvw_reviews WHERE review_id=%s FOR UPDATE", (review_id,)).fetchone()
    scope, project, version = db.execute("SELECT scope,project_id,lock_version FROM plm.rvw_review_rounds WHERE review_round_id=%s FOR UPDATE", (round_id,)).fetchone()
    assignment = db.execute("SELECT assignment_id FROM plm.rvw_review_assignments WHERE review_round_id=%s AND reviewer_id=%s", (round_id, reviewer)).fetchone()
    identity = insert(db, TABLES[3], dict(review_id=review_id, review_round_id=round_id, scope=scope, project_id=project,
        assignment_id=assignment[0] if assignment else uuid.uuid4(), reviewer_id=reviewer,
        decision=choice, comment=comment, decided_at=datetime.now(timezone.utc), trace_id=uuid.uuid4(),
        round_after_version=999, created_xid=1), "decision_id")
    assert db.execute("SELECT round_after_version=%s AND created_xid=txid_current() FROM plm.rvw_review_decisions WHERE decision_id=%s", (version+1, identity)).fetchone()[0]
    if omit != "assignment":
        db.execute("UPDATE plm.rvw_review_assignments SET assignment_state='DECIDED' WHERE assignment_id=%s", (assignment[0],))
    ac = db.execute("SELECT count(*) FROM plm.rvw_review_assignments WHERE review_round_id=%s", (round_id,)).fetchone()[0]
    dc, returned = db.execute("SELECT count(*),coalesce(bool_or(decision='RETURN'),false) FROM plm.rvw_review_decisions WHERE review_round_id=%s", (round_id,)).fetchone()
    state = force_state or ("IN_REVIEW" if dc < ac else "RETURNED" if returned else "APPROVED")
    if omit != "round":
        db.execute("UPDATE plm.rvw_review_rounds SET round_state=%s,lock_version=lock_version+1 WHERE review_round_id=%s", (state, round_id))
    if omit != "review":
        db.execute("UPDATE plm.rvw_reviews SET review_state=%s,active_round_id=%s,lock_version=lock_version+1 WHERE review_id=%s", (state, round_id if state == "IN_REVIEW" else None, review_id))
    if state != "IN_REVIEW" and omit != "lock":
        db.execute("UPDATE plm.rvw_subject_locks SET lock_state='RELEASED',released_at=statement_timestamp() WHERE review_round_id=%s", (round_id,))
    if omit != "event":
        event(db, scope, project, review_id, round_id, reviewer, "DECISION_RECORDED", version+1, state, identity)
        if state != "IN_REVIEW":
            event(db, scope, project, review_id, round_id, reviewer, "COMPLETED", version+1, state)
    return identity


def withdraw(db, round_id, actor, omit=None):
    review_id = db.execute("SELECT review_id FROM plm.rvw_review_rounds WHERE review_round_id=%s", (round_id,)).fetchone()[0]
    db.execute("SELECT 1 FROM plm.rvw_reviews WHERE review_id=%s FOR UPDATE", (review_id,)).fetchone()
    scope, project, version = db.execute("SELECT scope,project_id,lock_version FROM plm.rvw_review_rounds WHERE review_round_id=%s FOR UPDATE", (round_id,)).fetchone()
    db.execute("UPDATE plm.rvw_review_rounds SET round_state='WITHDRAWN',lock_version=lock_version+1 WHERE review_round_id=%s", (round_id,))
    db.execute("UPDATE plm.rvw_reviews SET review_state='WITHDRAWN',active_round_id=NULL,lock_version=lock_version+1 WHERE review_id=%s", (review_id,))
    if omit != "lock":
        db.execute("UPDATE plm.rvw_subject_locks SET lock_state='RELEASED',released_at=statement_timestamp() WHERE review_round_id=%s", (round_id,))
    if omit != "event":
        event(db, scope, project, review_id, round_id, actor, "WITHDRAWN", version+1, "WITHDRAWN")


def main():
    name = "reviewschema_"+uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config = create_migration_config(URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name))
            command.upgrade(config, "head")
            command.check(config)
            command.downgrade(config, "20260926_0033")
            command.upgrade(config, "head")
            command.downgrade(config, "20260926_0033")
            with connect(name) as db:
                users = [insert(db, "auth_users", dict(username_display=f"Synthetic Review {i}", username_normalized=f"synthetic review {i}"), "user_id") for i in range(4)]
                actor, *reviewers = users
                projects = [insert(db, "prj_projects", dict(project_code=f"RVW{i}", project_code_normalized=f"rvw{i}", name=f"Synthetic review project {i}", created_by=actor), "project_id") for i in range(2)]
                with db.transaction():
                    fixture.initialize(db, projects[0], actor)
                old = db.execute("SELECT * FROM plm.wfl_project_workflows").fetchall()
            command.upgrade(config, "head")
            with connect(name) as db:
                assert db.execute("SELECT * FROM plm.wfl_project_workflows").fetchall() == old
                assert all(db.execute(sql.SQL("SELECT count(*) FROM plm.{}").format(sql.Identifier(t))).fetchone()[0] == 0 for t in TABLES)
                evidence = fixture.seed_evidence(db, projects[0], actor)
                global_evidence = fixture.seed_evidence(db, None, actor)
                foreign_evidence = fixture.seed_evidence(db, projects[1], actor)
                identity = review(db, actor, projects[0])
                global_review = review(db, actor, None)
                for omit in ("assignments", "snapshot", "lock", "event", "review"):
                    reject(db, lambda omit=omit: start(db, identity, actor, reviewers, evidence, omit=omit))
                for values in (dict(project_id=projects[1]), dict(scope="GLOBAL", project_id=None), dict(round_no=9), dict(lock_version=1), dict(round_state="APPROVED")):
                    reject(db, lambda values=values: start(db, identity, actor, reviewers, evidence, changes=values))
                for values in (dict(ref_project_id=projects[1]), dict(content_fingerprint=b"x"*32), dict(observed_lock_version=99)):
                    reject(db, lambda values=values: start(db, identity, actor, reviewers, evidence, ref_changes=values))
                reject(db, lambda: start(db, identity, actor, reviewers, foreign_evidence))
                reject(db, lambda: start(db, global_review, actor, reviewers, evidence))
                reject(db, lambda: start(db, identity, actor, [reviewers[0], reviewers[0]], evidence))
                with db.transaction():
                    round_id, assignments, fixed = start(db, identity, actor, reviewers, evidence)
                reject(db, lambda: start(db, identity, actor, reviewers, evidence))
                for option in ("assignment", "round", "review", "lock", "event"):
                    if option == "lock":
                        continue
                    reject(db, lambda option=option: decide(db, round_id, reviewers[0], omit=option))
                reject(db, lambda: decide(db, round_id, reviewers[0], force_state="APPROVED"))
                reject(db, lambda: decide(db, round_id, actor))
                for comment in (None, "", " ", "\u3000"):
                    reject(db, lambda comment=comment: decide(db, round_id, reviewers[0], "RETURN", comment=comment))
                with db.transaction():
                    first = decide(db, round_id, reviewers[0], "RETURN", comment="Synthetic substantive return")
                assert db.execute("SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s", (round_id,)).fetchone()[0] == "IN_REVIEW"
                assert db.execute("SELECT lock_state FROM plm.rvw_subject_locks WHERE review_round_id=%s", (round_id,)).fetchone()[0] == "ACTIVE"
                reject(db, lambda: decide(db, round_id, reviewers[0]))
                with db.transaction():
                    decide(db, round_id, reviewers[1])
                reject(db, lambda: decide(db, round_id, reviewers[2], omit="lock"))
                with db.transaction():
                    decide(db, round_id, reviewers[2])
                assert db.execute("SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s", (round_id,)).fetchone()[0] == "RETURNED"
                reject(db, lambda: start(db, identity, actor, reviewers, evidence, version=fixed))
                with db.transaction():
                    second_round, _, _ = start(db, identity, actor, reviewers, global_evidence)
                with db.transaction():
                    decide(db, second_round, reviewers[0])
                reject(db, lambda: withdraw(db, second_round, actor, omit="lock"))
                reject(db, lambda: withdraw(db, second_round, actor, omit="event"))
                with db.transaction():
                    withdraw(db, second_round, actor)
                assert db.execute("SELECT count(*) FROM plm.rvw_review_assignments WHERE review_round_id=%s AND assignment_state='PENDING'", (second_round,)).fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.rvw_review_decisions WHERE decision_id=%s", (first,)).fetchone()[0] == 1
                with db.transaction():
                    global_round, _, _ = start(db, global_review, actor, reviewers[:1], global_evidence)
                assert db.execute("SELECT scope_project_key FROM plm.rvw_review_rounds WHERE review_round_id=%s", (global_round,)).fetchone()[0].int == 0
                with db.transaction():
                    decide(db, global_round, reviewers[0])
                assert db.execute("SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s", (global_round,)).fetchone()[0] == "APPROVED"
                # GLOBAL child/circular FK cannot silently skip because ProjectId is NULL.
                other_global = review(db, actor, None)
                def wrong_global_pointer():
                    db.execute("UPDATE plm.rvw_reviews SET review_state='IN_REVIEW',active_round_id=%s,lock_version=1 WHERE review_id=%s", (global_round, other_global))
                    db.execute("SET CONSTRAINTS plm.fk_rvw_reviews__active_round IMMEDIATE")
                reject(db, wrong_global_pointer)
                # Committed round child sets and terminal events are sealed.
                reject(db, lambda: insert(db, TABLES[2], dict(review_id=global_review, review_round_id=global_round,
                    scope="GLOBAL", project_id=None, reviewer_id=reviewers[1]), "assignment_id"))
                reject(db, lambda: event(db, "GLOBAL", None, global_review, global_round, actor, "COMPLETED", 1, "APPROVED"))
                # Same logical identity cannot acquire two active locks through different Reviews.
                subject = uuid.uuid4()
                one, two = review(db, actor, projects[0], subject), review(db, actor, projects[0], subject)
                with db.transaction():
                    locked_round, _, _ = start(db, one, actor, reviewers[:1], evidence)
                reject(db, lambda: start(db, two, actor, reviewers[:1], evidence))
                with db.transaction():
                    withdraw(db, locked_round, actor)
                    start(db, two, actor, reviewers[:1], evidence)
                # Trace observation is based on true immutable edge metadata, never a fake source lock.
                trace_review = review(db, actor, projects[0])
                target = db.execute("SELECT subject_id FROM plm.rvw_reviews WHERE review_id=%s", (trace_review,)).fetchone()[0]
                doc, doc_version = db.execute("SELECT document_id,document_version_id FROM plm.evd_evidence_records WHERE evidence_id=%s", (evidence,)).fetchone()
                trace_version = uuid.uuid4()
                trace = insert(db, "trc_links", dict(scope="PROJECT", project_id=projects[0],
                    source_owner_module="document", source_object_type="DOC-02", source_object_id=doc,
                    source_version_id=doc_version, source_project_id=projects[0], target_owner_module="handover",
                    target_object_type="HND-02", target_object_id=target, target_version_id=trace_version,
                    target_project_id=projects[0], relation_type="DERIVED_FROM", created_by=actor, trace_id=uuid.uuid4()), "trace_link_id")
                reject(db, lambda: start(db, trace_review, actor, reviewers[:1], trace=trace, version=trace_version,
                                         ref_changes=dict(observed_lock_version=1)))
                reject(db, lambda: start(db, trace_review, actor, reviewers[:1], trace=trace, version=trace_version,
                                         ref_changes=dict(content_fingerprint=b"x"*32)))
                with db.transaction():
                    trace_round, _, _ = start(db, trace_review, actor, reviewers[:1], trace=trace, version=trace_version)
                assert db.execute("SELECT observed_lock_version,content_fingerprint=plm.review_trace_fingerprint(t) FROM plm.rvw_subject_snapshot_refs r JOIN plm.trc_links t ON t.trace_link_id=r.trace_link_id WHERE review_round_id=%s", (trace_round,)).fetchone() == (0, True)
                db.execute("UPDATE plm.trc_links SET link_state='REVOKED' WHERE trace_link_id=%s", (trace,))
                assert db.execute("SELECT observed_state FROM plm.rvw_subject_snapshot_refs WHERE review_round_id=%s", (trace_round,)).fetchone()[0] == "ACTIVE"
                # Record/Audit-shaped failure leaves no decision/projection/lock/event residue.
                before = snapshot(db)
                try:
                    with db.transaction():
                        decide(db, trace_round, reviewers[0])
                        raise RuntimeError("Synthetic Audit failure")
                except RuntimeError:
                    assert snapshot(db) == before
                # Final decide vs withdraw serializes on Review, with exactly one terminal winner.
                barrier = Barrier(2)
                def competing(which):
                    try:
                        with connect(name) as rival, rival.transaction():
                            barrier.wait(timeout=10)
                            if which:
                                decide(rival, trace_round, reviewers[0])
                            else:
                                withdraw(rival, trace_round, actor)
                        return "success"
                    except psycopg.Error as exc:
                        assert exc.sqlstate == "P0001" and ("current Assignment invalid" in exc.diag.message_primary or "sealed or state invalid" in exc.diag.message_primary)
                        return "closed"
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert sorted(pool.map(competing, (0, 1))) == ["closed", "success"]
                assert db.execute("SELECT lock_state FROM plm.rvw_subject_locks WHERE review_round_id=%s", (trace_round,)).fetchone()[0] == "RELEASED"
                # Distinct reviewers can decide concurrently without losing either result.
                multi_review = review(db, actor, projects[0])
                with db.transaction():
                    multi_round, _, _ = start(db, multi_review, actor, reviewers, global_evidence)
                barrier = Barrier(2)
                def distinct(user):
                    with connect(name) as rival, rival.transaction():
                        barrier.wait(timeout=10)
                        decide(rival, multi_round, user)
                    return "success"
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert list(pool.map(distinct, reviewers[:2])) == ["success", "success"]
                assert db.execute("SELECT round_state,lock_version FROM plm.rvw_review_rounds WHERE review_round_id=%s", (multi_round,)).fetchone() == ("IN_REVIEW", 2)
                with db.transaction():
                    decide(db, multi_round, reviewers[2])
                assert db.execute("SELECT round_state,lock_version FROM plm.rvw_review_rounds WHERE review_round_id=%s", (multi_round,)).fetchone() == ("APPROVED", 3)
                # Source observation is rechecked at start commit, not just at ref INSERT.
                changed_review = review(db, actor, projects[0])
                def change_source_before_commit():
                    start(db, changed_review, actor, reviewers[:1], evidence)
                    db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',eligibility_reason='Synthetic before commit',updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s", (actor, evidence))
                reject(db, change_source_before_commit)
                # Actual generated columns are ALWAYS and GLOBAL joins retained a real zero key.
                assert db.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='plm' AND table_name LIKE 'rvw_%' AND column_name='scope_project_key' AND is_generated='ALWAYS'").fetchone()[0] == 8
                assert db.execute("SELECT count(*) FROM plm.rvw_subject_snapshot_refs WHERE evidence_id IS DISTINCT FROM CASE WHEN ref_kind='EVIDENCE' THEN ref_id ELSE NULL END OR trace_link_id IS DISTINCT FROM CASE WHEN ref_kind='TRACE_LINK' THEN ref_id ELSE NULL END").fetchone()[0] == 0
                for table in TABLES:
                    reject(db, lambda table=table: db.execute(sql.SQL("DELETE FROM plm.{}").format(sql.Identifier(table))))
                    reject(db, lambda table=table: db.execute(sql.SQL("TRUNCATE plm.{} CASCADE").format(sql.Identifier(table))))
                for table in (TABLES[3], TABLES[4], TABLES[5], TABLES[7]):
                    reject(db, lambda table=table: db.execute(sql.SQL("UPDATE plm.{} SET review_id=review_id").format(sql.Identifier(table))))
                retained = snapshot(db)
            try:
                command.downgrade(config, "20260926_0033")
            except RuntimeError as exc:
                assert "Review history exists" in str(exc)
            else:
                raise AssertionError("nonempty Review down accepted")
            command.check(config)
            with connect(name) as db:
                assert snapshot(db) == retained
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260926_0034"
            print("Review 0034 PASS: eight-table ORM/empty/existing upgrade, scopes/complete-set/history/withdrawal/ref facts and nonempty down; synthetic Subjects/reviewer identity only")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
