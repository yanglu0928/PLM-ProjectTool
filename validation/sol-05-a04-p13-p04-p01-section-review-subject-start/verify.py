"""Disposable Win11/PG18 proof of the SOL-05 START repository contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.solution.infrastructure.section_review_repository import (
    SqlAlchemySectionReviewSubjectRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_review_start_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    actor, project, outline, section, version, review, round_id = (
        uuid.uuid4() for _ in range(7))
    fingerprint = b"s" * 32
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    # Fixtures use synthetic identities only. Disable creation Owner triggers
    # for setup, then exercise the actual START guards with normal role.
    with psycopg.connect(**connection) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized) VALUES (%s,'Start Actor','start actor')",
                (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'SRSTART','srstart','Start Fixture',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,"
                "name,created_by) VALUES (%s,%s,'Fixture Outline',%s)",
                (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,"
                "solution_outline_id,project_id,section_key,created_by) "
                "VALUES (%s,%s,%s,'fixture',%s)",
                (section, outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_section_versions("
                "solution_section_version_id,solution_section_id,project_id,"
                "version_no,title,content_artifact_ref,content_fingerprint,"
                "assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,spec_binding_state,"
                "spec_not_required_reason,created_by) VALUES "
                "(%s,%s,%s,1,'Fixture Section',%s,%s,'[]','[]',0,0,"
                "'NONE_REQUIRED','No structured spec',%s)",
                (version, section, project, uuid.uuid4(), fingerprint, actor))
            db.execute(
                "INSERT INTO plm.sol_section_version_create_results("
                "solution_section_version_id,solution_section_id,project_id,"
                "version_no,title,content_artifact_ref,content_fingerprint,"
                "assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by,created_at) "
                "SELECT solution_section_version_id,solution_section_id,"
                "project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,"
                "declared_requirement_count,declared_evidence_count,"
                "created_by,created_at FROM plm.sol_section_versions "
                "WHERE solution_section_version_id=%s", (version,))
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,"
                "subject_type,subject_id,policy_code,review_state,"
                "active_round_id,created_by) "
                "VALUES (%s,'PROJECT',%s,'SOL-05',%s,"
                "'SOLUTION_SECTION_ALL_V1','IN_REVIEW',%s,%s)",
                (review, project, section, round_id, actor))
            db.execute(
                "INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,"
                "scope,project_id,round_no,subject_version_id,round_state,"
                "started_by,started_at) VALUES "
                "(%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',%s,statement_timestamp())",
                (round_id, review, project, version, actor))
            db.execute(
                "INSERT INTO plm.rvw_subject_snapshots(review_id,"
                "review_round_id,scope,project_id,subject_type,subject_id,"
                "subject_version_id,content_fingerprint,proof_schema_version,"
                "verified_at) VALUES "
                "(%s,%s,'PROJECT',%s,'SOL-05',%s,%s,%s,1,statement_timestamp())",
                (review, round_id, project, section, version, fingerprint))
    runtime = create_database_runtime(url)
    repository = SqlAlchemySectionReviewSubjectRepository()
    try:
        with runtime.unit_of_work() as tx:
            assert repository.section_exists(
                tx, project_id=project, section_id=section)
            assert repository.version_exists(
                tx, project_id=project, section_id=section,
                version_id=version)
            assert repository.lock_subject(
                tx, project_id=uuid.uuid4(), section_id=section,
                version_id=version) is None
            locked = repository.lock_subject(
                tx, project_id=project, section_id=section,
                version_id=version)
            assert locked is not None and locked.latest_version_id == version
            assert locked.version.content_fingerprint == fingerprint
            repository.bind_start(
                tx, before=locked, review_id=review,
                round_id=round_id, actor_id=actor)
            active = repository.lock_subject(
                tx, project_id=project, section_id=section,
                version_id=version)
            assert active is not None and active.version.version_state == "IN_REVIEW"
            assert active.version.review_ref == review
            tx.commit()
        with psycopg.connect(**connection) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.sol_section_review_state_results "
                "WHERE solution_section_version_id=%s AND event_type='START'",
                (version,)).fetchone()[0] == 1
            assert db.execute(
                "SELECT version_state FROM plm.sol_section_versions "
                "WHERE solution_section_version_id=%s", (version,)
            ).fetchone()[0] == "IN_REVIEW"
        print("SOL_05_A04_P13_P04_P01_SECTION_REVIEW_START_PG_PASS")
    finally:
        runtime.dispose()


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
