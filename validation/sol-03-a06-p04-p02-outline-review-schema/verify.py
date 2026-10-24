"""Disposable Win11/PG18 Outline Review state/result closure proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_review_schema_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261023_0184"
TARGET = "20261024_0185"


def _seed_version(db, *, actor, project, outline, version, number,
                  fingerprint, previous=None) -> None:
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.sol_outline_versions("
            "solution_outline_version_id,solution_outline_id,project_id,"
            "version_no,content_fingerprint,missing_declarations,"
            "conflict_declarations,declared_section_count,"
            "declared_requirement_count,declared_reference_count,"
            "supersedes_version_ref,created_by) "
            "VALUES (%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,1,1,0,%s,%s)",
            (version, outline, project, number, fingerprint, previous, actor))


def _seed_review(db, *, actor, project, outline, version, fingerprint):
    review, round_id = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
            "subject_id,policy_code,review_state,active_round_id,created_by) "
            "VALUES (%s,'PROJECT',%s,'SOL-03',%s,'SOLUTION_OUTLINE_ALL_V1',"
            "'IN_REVIEW',%s,%s)",
            (review, project, outline, round_id, actor))
        db.execute(
            "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
            "project_id,round_no,subject_version_id,round_state,started_by,"
            "started_at) VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',%s,"
            "statement_timestamp())",
            (round_id, review, project, version, actor))
        db.execute(
            "INSERT INTO plm.rvw_subject_snapshots(review_id,review_round_id,"
            "scope,project_id,subject_type,subject_id,subject_version_id,"
            "content_fingerprint,proof_schema_version,verified_at) "
            "VALUES (%s,%s,'PROJECT',%s,'SOL-03',%s,%s,%s,1,"
            "statement_timestamp())",
            (review, round_id, project, outline, version, fingerprint))
    return review, round_id


def _result(db, *, version, outline, project, review, round_id, event,
            previous, current, actor) -> None:
    db.execute(
        "INSERT INTO plm.sol_outline_review_state_results("
        "solution_outline_version_id,solution_outline_id,project_id,review_id,"
        "review_round_id,event_type,previous_approved_version_ref,"
        "current_approved_version_ref,actor_id) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (version, outline, project, review, round_id, event,
         previous, current, actor))


def _start(db, *, version, outline, project, review, round_id, previous,
           actor) -> None:
    with db.transaction():
        db.execute(
            "UPDATE plm.sol_outline_versions SET version_state='IN_REVIEW',"
            "review_ref=%s,review_round_ref=%s "
            "WHERE solution_outline_version_id=%s", (review, round_id, version))
        _result(db, version=version, outline=outline, project=project,
                review=review, round_id=round_id, event="START",
                previous=previous, current=previous, actor=actor)


def _finish_review(db, *, review, round_id, project, actor, state) -> None:
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.rvw_reviews SET review_state=%s,active_round_id=NULL "
            "WHERE review_id=%s", (state, review))
        db.execute("UPDATE plm.rvw_review_rounds SET round_state=%s "
                   "WHERE review_round_id=%s", (state, round_id))
        db.execute(
            "INSERT INTO plm.rvw_round_events(review_id,review_round_id,"
            "scope,project_id,event_type,actor_id,trace_id,occurred_at,"
            "before_lock_version,after_lock_version,result_state,"
            "withdrawal_reason) "
            "VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,"
            "statement_timestamp(),0,1,%s,%s)",
            (review, round_id, project,
             "WITHDRAWN" if state == "WITHDRAWN" else "COMPLETED",
             actor, uuid.uuid4(), state,
             "Synthetic withdrawal" if state == "WITHDRAWN" else None))


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, TARGET)
    command.downgrade(cfg, PREVIOUS)

    actor, project, outline, first = (uuid.uuid4() for _ in range(4))
    with psycopg.connect(**connection) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized) VALUES (%s,'Outline Review Actor',"
                "'outline review actor')", (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'OR185','or185','Outline Review Fixture',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,"
                "name,created_by) VALUES (%s,%s,'Fixture Outline',%s)",
                (outline, project, actor))
        _seed_version(db, actor=actor, project=project, outline=outline,
                      version=first, number=1, fingerprint=b"f" * 32)
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        review, round_id = _seed_review(
            db, actor=actor, project=project, outline=outline,
            version=first, fingerprint=b"f" * 32)
        fixture.rejects(
            "OutlineVersion Review transition has no immutable result",
            lambda: db.execute(
                "UPDATE plm.sol_outline_versions SET version_state='IN_REVIEW',"
                "review_ref=%s,review_round_ref=%s "
                "WHERE solution_outline_version_id=%s",
                (review, round_id, first)))
        fixture.rejects(
            "Outline approval pointer is outside Review Owner",
            lambda: db.execute(
                "UPDATE plm.sol_outlines SET current_approved_version_ref=%s,"
                "lock_version=1 WHERE solution_outline_id=%s",
                (first, outline)))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE review_round_id=%s", (b"x" * 32, round_id))
        fixture.rejects(
            "Outline Review result does not match current facts",
            lambda: _start(db, version=first, outline=outline, project=project,
                           review=review, round_id=round_id,
                           previous=None, actor=actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                "WHERE review_round_id=%s", (b"f" * 32, round_id))
            db.execute(
                "UPDATE plm.rvw_reviews SET policy_code='WRONG_POLICY' "
                "WHERE review_id=%s", (review,))
        fixture.rejects(
            "Outline Review result does not match current facts",
            lambda: _start(db, version=first, outline=outline, project=project,
                           review=review, round_id=round_id,
                           previous=None, actor=actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.rvw_reviews SET policy_code='SOLUTION_OUTLINE_ALL_V1' "
                "WHERE review_id=%s", (review,))
        _start(db, version=first, outline=outline, project=project,
               review=review, round_id=round_id, previous=None, actor=actor)
        fixture.rejects(
            "OutlineVersion cannot be created during Review",
            lambda: db.execute(
                "INSERT INTO plm.sol_outline_versions("
                "solution_outline_version_id,solution_outline_id,project_id,"
                "version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,"
                "declared_requirement_count,declared_reference_count,"
                "supersedes_version_ref,created_by) VALUES "
                "(%s,%s,%s,2,%s,'[]'::jsonb,'[]'::jsonb,1,1,0,%s,%s)",
                (uuid.uuid4(), outline, project, b"i" * 32, first, actor)))
        fixture.rejects(
            "OutlineVersion update is outside Review Owner",
            lambda: db.execute(
                "UPDATE plm.sol_outline_versions SET content_fingerprint=%s "
                "WHERE solution_outline_version_id=%s", (b"z" * 32, first)))
        fixture.rejects(
            "Outline Review result history is immutable",
            lambda: db.execute(
                "UPDATE plm.sol_outline_review_state_results "
                "SET event_type='RETURNED' WHERE event_type='START'"))
        _finish_review(db, review=review, round_id=round_id,
                       project=project, actor=actor, state="APPROVED")
        fixture.rejects(
            "OutlineVersion Review transition has no immutable result",
            lambda: db.execute(
                "UPDATE plm.sol_outline_versions SET version_state='APPROVED' "
                "WHERE solution_outline_version_id=%s", (first,)))
        with db.transaction():
            db.execute("UPDATE plm.sol_outline_versions SET version_state='APPROVED' "
                       "WHERE solution_outline_version_id=%s", (first,))
            db.execute(
                "UPDATE plm.sol_outlines SET current_approved_version_ref=%s,"
                "lock_version=lock_version+1 WHERE solution_outline_id=%s",
                (first, outline))
            _result(db, version=first, outline=outline, project=project,
                    review=review, round_id=round_id, event="APPROVED",
                    previous=None, current=first, actor=actor)
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_outlines "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == first
        returned = uuid.uuid4()
        _seed_version(db, actor=actor, project=project, outline=outline,
                      version=returned, number=2, fingerprint=b"r" * 32,
                      previous=first)
        returned_review, returned_round = _seed_review(
            db, actor=actor, project=project, outline=outline,
            version=returned, fingerprint=b"r" * 32)
        _start(db, version=returned, outline=outline, project=project,
               review=returned_review, round_id=returned_round,
               previous=first, actor=actor)
        _finish_review(db, review=returned_review, round_id=returned_round,
                       project=project, actor=actor, state="RETURNED")
        with db.transaction():
            db.execute("UPDATE plm.sol_outline_versions SET version_state='RETURNED' "
                       "WHERE solution_outline_version_id=%s", (returned,))
            _result(db, version=returned, outline=outline, project=project,
                    review=returned_review, round_id=returned_round,
                    event="RETURNED", previous=first, current=first, actor=actor)
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_outlines "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == first
        replacement = uuid.uuid4()
        _seed_version(db, actor=actor, project=project, outline=outline,
                      version=replacement, number=3, fingerprint=b"n" * 32,
                      previous=returned)
        replacement_review, replacement_round = _seed_review(
            db, actor=actor, project=project, outline=outline,
            version=replacement, fingerprint=b"n" * 32)
        _start(db, version=replacement, outline=outline, project=project,
               review=replacement_review, round_id=replacement_round,
               previous=first, actor=actor)
        _finish_review(db, review=replacement_review,
                       round_id=replacement_round, project=project,
                       actor=actor, state="APPROVED")
        with db.transaction():
            db.execute("UPDATE plm.sol_outline_versions "
                       "SET version_state='SUPERSEDED' "
                       "WHERE solution_outline_version_id=%s", (first,))
            db.execute("UPDATE plm.sol_outline_versions "
                       "SET version_state='APPROVED' "
                       "WHERE solution_outline_version_id=%s", (replacement,))
            db.execute(
                "UPDATE plm.sol_outlines SET current_approved_version_ref=%s,"
                "lock_version=lock_version+1 WHERE solution_outline_id=%s",
                (replacement, outline))
            _result(db, version=replacement, outline=outline, project=project,
                    review=replacement_review, round_id=replacement_round,
                    event="APPROVED", previous=first, current=replacement,
                    actor=actor)
        assert db.execute(
            "SELECT version_state FROM plm.sol_outline_versions "
            "WHERE solution_outline_version_id=%s", (first,)).fetchone()[0] == (
                "SUPERSEDED")
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_outlines "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == (
                replacement)
        withdrawn = uuid.uuid4()
        _seed_version(db, actor=actor, project=project, outline=outline,
                      version=withdrawn, number=4, fingerprint=b"w" * 32,
                      previous=replacement)
        withdrawn_review, withdrawn_round = _seed_review(
            db, actor=actor, project=project, outline=outline,
            version=withdrawn, fingerprint=b"w" * 32)
        _start(db, version=withdrawn, outline=outline, project=project,
               review=withdrawn_review, round_id=withdrawn_round,
               previous=replacement, actor=actor)
        _finish_review(db, review=withdrawn_review,
                       round_id=withdrawn_round, project=project,
                       actor=actor, state="WITHDRAWN")
        with db.transaction():
            db.execute("UPDATE plm.sol_outline_versions "
                       "SET version_state='RETURNED' "
                       "WHERE solution_outline_version_id=%s", (withdrawn,))
            _result(db, version=withdrawn, outline=outline, project=project,
                    review=withdrawn_review, round_id=withdrawn_round,
                    event="WITHDRAWN", previous=replacement,
                    current=replacement, actor=actor)
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.sol_outlines "
            "WHERE solution_outline_id=%s", (outline,)).fetchone()[0] == (
                replacement)
        fixture.rejects(
            "Outline Review state history prevents downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_03_A06_P04_P02_OUTLINE_REVIEW_SCHEMA_PASS: "
          "empty/existing upgrade, no-history downgrade, "
          "START/APPROVED/RETURNED/WITHDRAWN/SUPERSEDED closure, "
          "wrong snapshot/policy/direct mutation/in-review create rejection, "
          "history-safe downgrade, drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
