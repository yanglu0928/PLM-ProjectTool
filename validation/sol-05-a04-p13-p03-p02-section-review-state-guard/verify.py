"""Disposable Win11/PG18 Section Review state/result closure proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_review_state_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261023_0183"
TARGET = "20261023_0184"


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

    actor, project, outline, section, version, review, round_id = (
        uuid.uuid4() for _ in range(7))
    fingerprint = b"s" * 32
    with psycopg.connect(**connection) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'Section State Actor','section state actor')", (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'SR184','sr184','Section State Fixture',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Fixture Outline',%s)", (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'fixture',%s)",
                (section, outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,1,'Fixture Section',%s,%s,'[]','[]',0,0,%s)",
                (version, section, project, uuid.uuid4(), fingerprint, actor))
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
                "subject_id,policy_code,review_state,active_round_id,created_by) "
                "VALUES (%s,'PROJECT',%s,'SOL-05',%s,'SOLUTION_SECTION_ALL_V1',"
                "'IN_REVIEW',%s,%s)", (review, project, section, round_id, actor))
            db.execute(
                "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
                "project_id,round_no,subject_version_id,round_state,started_by,started_at) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',%s,statement_timestamp())",
                (round_id, review, project, version, actor))
            db.execute(
                "INSERT INTO plm.rvw_subject_snapshots(review_id,review_round_id,scope,"
                "project_id,subject_type,subject_id,subject_version_id,"
                "content_fingerprint,proof_schema_version,verified_at) "
                "VALUES (%s,%s,'PROJECT',%s,'SOL-05',%s,%s,%s,1,statement_timestamp())",
                (review, round_id, project, section, version, fingerprint))
        def start_update():
            with db.transaction():
                db.execute(
                    "UPDATE plm.sol_section_versions SET version_state='IN_REVIEW',"
                    "review_ref=%s,review_round_ref=%s "
                    "WHERE solution_section_version_id=%s", (review, round_id, version))
        fixture.rejects("SectionVersion Review transition has no immutable result",
                        start_update)
        assert db.execute("SELECT version_state FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s", (version,)).fetchone()[0] == "DRAFT"
        fixture.rejects("Section approval pointer is outside Review Owner",
                        lambda: db.execute(
                            "UPDATE plm.sol_sections SET current_approved_version_ref=%s,"
                            "lock_version=1 WHERE solution_section_id=%s", (version, section)))
        insert = (
            "INSERT INTO plm.sol_section_review_state_results("
            "solution_section_version_id,solution_section_id,project_id,review_id,"
            "review_round_id,event_type,previous_approved_version_ref,"
            "current_approved_version_ref,actor_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        def start_valid():
            with db.transaction():
                db.execute(
                    "UPDATE plm.sol_section_versions SET version_state='IN_REVIEW',"
                    "review_ref=%s,review_round_ref=%s "
                    "WHERE solution_section_version_id=%s", (review, round_id, version))
                db.execute(insert, (version, section, project, review, round_id,
                                    "START", None, None, actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                       "WHERE review_round_id=%s", (b"wrong".ljust(32, b"x"), round_id))
        fixture.rejects("Section Review result does not match current facts",
                        start_valid)
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.rvw_subject_snapshots SET content_fingerprint=%s "
                       "WHERE review_round_id=%s", (fingerprint, round_id))
        start_valid()
        assert db.execute("SELECT version_state,review_ref FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s", (version,)).fetchone() == (
                              "IN_REVIEW", review)
        fixture.rejects("Section Review result history is immutable",
                        lambda: db.execute(
                            "UPDATE plm.sol_section_review_state_results "
                            "SET event_type='RETURNED' WHERE event_type='START'"))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                       "active_round_id=NULL WHERE review_id=%s", (review,))
            db.execute("UPDATE plm.rvw_review_rounds SET round_state='APPROVED' "
                       "WHERE review_round_id=%s", (round_id,))
            db.execute(
                "INSERT INTO plm.rvw_round_events(review_id,review_round_id,scope,"
                "project_id,event_type,actor_id,trace_id,occurred_at,"
                "before_lock_version,after_lock_version,result_state) "
                "VALUES (%s,%s,'PROJECT',%s,'COMPLETED',%s,%s,statement_timestamp(),"
                "0,1,'APPROVED')",
                (review, round_id, project, actor, uuid.uuid4()))
        def approve_without_result():
            with db.transaction():
                db.execute("UPDATE plm.sol_section_versions SET version_state='APPROVED' "
                           "WHERE solution_section_version_id=%s", (version,))
        fixture.rejects("SectionVersion Review transition has no immutable result",
                        approve_without_result)
        with db.transaction():
            db.execute("UPDATE plm.sol_section_versions SET version_state='APPROVED' "
                       "WHERE solution_section_version_id=%s", (version,))
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=%s,"
                       "lock_version=lock_version+1 WHERE solution_section_id=%s",
                       (version, section))
            db.execute(insert, (version, section, project, review, round_id,
                                "APPROVED", None, version, actor))
        assert db.execute("SELECT current_approved_version_ref FROM plm.sol_sections "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == version
        returned_version, returned_review, returned_round = (
            uuid.uuid4() for _ in range(3))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,supersedes_version_ref,created_by) "
                "VALUES (%s,%s,%s,2,'Returned Section',%s,%s,'[]','[]',0,0,%s,%s)",
                (returned_version, section, project, uuid.uuid4(), b"r" * 32,
                 version, actor))
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
                "subject_id,policy_code,review_state,active_round_id,created_by) "
                "VALUES (%s,'PROJECT',%s,'SOL-05',%s,'SOLUTION_SECTION_ALL_V1',"
                "'IN_REVIEW',%s,%s)",
                (returned_review, project, section, returned_round, actor))
            db.execute(
                "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
                "project_id,round_no,subject_version_id,round_state,started_by,started_at) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',%s,statement_timestamp())",
                (returned_round, returned_review, project, returned_version, actor))
            db.execute(
                "INSERT INTO plm.rvw_subject_snapshots(review_id,review_round_id,scope,"
                "project_id,subject_type,subject_id,subject_version_id,"
                "content_fingerprint,proof_schema_version,verified_at) "
                "VALUES (%s,%s,'PROJECT',%s,'SOL-05',%s,%s,%s,1,statement_timestamp())",
                (returned_review, returned_round, project, section,
                 returned_version, b"r" * 32))
        with db.transaction():
            db.execute(
                "UPDATE plm.sol_section_versions SET version_state='IN_REVIEW',"
                "review_ref=%s,review_round_ref=%s "
                "WHERE solution_section_version_id=%s",
                (returned_review, returned_round, returned_version))
            db.execute(insert, (returned_version, section, project,
                                returned_review, returned_round,
                                "START", version, version, actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.rvw_reviews SET review_state='RETURNED',"
                       "active_round_id=NULL WHERE review_id=%s", (returned_review,))
            db.execute("UPDATE plm.rvw_review_rounds SET round_state='RETURNED' "
                       "WHERE review_round_id=%s", (returned_round,))
            db.execute(
                "INSERT INTO plm.rvw_round_events(review_id,review_round_id,scope,"
                "project_id,event_type,actor_id,trace_id,occurred_at,"
                "before_lock_version,after_lock_version,result_state) "
                "VALUES (%s,%s,'PROJECT',%s,'COMPLETED',%s,%s,statement_timestamp(),"
                "0,1,'RETURNED')",
                (returned_review, returned_round, project, actor, uuid.uuid4()))
        with db.transaction():
            db.execute("UPDATE plm.sol_section_versions SET version_state='RETURNED' "
                       "WHERE solution_section_version_id=%s", (returned_version,))
            db.execute(insert, (returned_version, section, project,
                                returned_review, returned_round,
                                "RETURNED", version, version, actor))
        assert db.execute("SELECT version_state FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s",
                          (returned_version,)).fetchone()[0] == "RETURNED"
        assert db.execute("SELECT current_approved_version_ref FROM plm.sol_sections "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == version
        replacement, replacement_review, replacement_round = (
            uuid.uuid4() for _ in range(3))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,supersedes_version_ref,created_by) "
                "VALUES (%s,%s,%s,3,'Replacement Section',%s,%s,'[]','[]',0,0,%s,%s)",
                (replacement, section, project, uuid.uuid4(), b"n" * 32,
                 returned_version, actor))
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,"
                "subject_id,policy_code,review_state,active_round_id,created_by) "
                "VALUES (%s,'PROJECT',%s,'SOL-05',%s,'SOLUTION_SECTION_ALL_V1',"
                "'IN_REVIEW',%s,%s)",
                (replacement_review, project, section, replacement_round, actor))
            db.execute(
                "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,"
                "project_id,round_no,subject_version_id,round_state,started_by,started_at) "
                "VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',%s,statement_timestamp())",
                (replacement_round, replacement_review, project, replacement, actor))
            db.execute(
                "INSERT INTO plm.rvw_subject_snapshots(review_id,review_round_id,scope,"
                "project_id,subject_type,subject_id,subject_version_id,"
                "content_fingerprint,proof_schema_version,verified_at) "
                "VALUES (%s,%s,'PROJECT',%s,'SOL-05',%s,%s,%s,1,statement_timestamp())",
                (replacement_review, replacement_round, project, section,
                 replacement, b"n" * 32))
        with db.transaction():
            db.execute(
                "UPDATE plm.sol_section_versions SET version_state='IN_REVIEW',"
                "review_ref=%s,review_round_ref=%s "
                "WHERE solution_section_version_id=%s",
                (replacement_review, replacement_round, replacement))
            db.execute(insert, (replacement, section, project,
                                replacement_review, replacement_round,
                                "START", version, version, actor))
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                       "active_round_id=NULL WHERE review_id=%s", (replacement_review,))
            db.execute("UPDATE plm.rvw_review_rounds SET round_state='APPROVED' "
                       "WHERE review_round_id=%s", (replacement_round,))
            db.execute(
                "INSERT INTO plm.rvw_round_events(review_id,review_round_id,scope,"
                "project_id,event_type,actor_id,trace_id,occurred_at,"
                "before_lock_version,after_lock_version,result_state) "
                "VALUES (%s,%s,'PROJECT',%s,'COMPLETED',%s,%s,statement_timestamp(),"
                "0,1,'APPROVED')",
                (replacement_review, replacement_round, project, actor, uuid.uuid4()))
        with db.transaction():
            db.execute("UPDATE plm.sol_section_versions SET version_state='SUPERSEDED' "
                       "WHERE solution_section_version_id=%s", (version,))
            db.execute("UPDATE plm.sol_section_versions SET version_state='APPROVED' "
                       "WHERE solution_section_version_id=%s", (replacement,))
            db.execute("UPDATE plm.sol_sections SET current_approved_version_ref=%s,"
                       "lock_version=lock_version+1 WHERE solution_section_id=%s",
                       (replacement, section))
            db.execute(insert, (replacement, section, project,
                                replacement_review, replacement_round,
                                "APPROVED", version, replacement, actor))
        assert db.execute(
            "SELECT version_state FROM plm.sol_section_versions "
            "WHERE solution_section_version_id=%s", (version,)).fetchone()[0] == "SUPERSEDED"
        assert db.execute("SELECT current_approved_version_ref FROM plm.sol_sections "
                          "WHERE solution_section_id=%s", (section,)).fetchone()[0] == replacement
        fixture.rejects("Section Review state history prevents downgrade",
                        lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_05_A04_P13_P03_P02_SECTION_REVIEW_STATE_GUARD_PASS: "
          "empty/existing upgrade, exact START/APPROVED/RETURNED/SUPERSEDED "
          "closure, direct mutation "
          "rejection, history-safe downgrade and ORM drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
