"""Disposable PG18 proof of Outline Review repository atomic lifecycle."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
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
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.solution.infrastructure.outline_review_repository import (
    SqlAlchemyOutlineReviewSubjectRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_review_repository_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def _transition(*, project, outline, version, actor, review, round_id,
                fingerprint):
    now = datetime.now(timezone.utc)
    progress = ReviewRoundProgress(round_id, now, (actor,))
    identity = ReviewIdentitySnapshot(
        review, "PROJECT", project, "SOL-03", outline,
        "SOLUTION_OUTLINE_ALL_V1", "IN_REVIEW", round_id, 1)
    before = FixedReviewRoundSnapshot(
        identity, 1, version, actor, progress, (uuid.uuid4(),), 0,
        uuid.uuid4(), fingerprint, 1, now, (), uuid.uuid4(), now, None)
    decision = ReviewDecisionSnapshot(
        uuid.uuid4(), round_id, actor, ReviewDecisionKind.APPROVE, now, None)
    return ReviewSubjectTransition(
        actor, uuid.uuid4(), before, progress.record_decision(decision),
        now, None)


def verify(port: int) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    actor, project, outline, version, review, round_id = (
        uuid.uuid4() for _ in range(6))
    fingerprint = b"o" * 32
    conn = dict(host="127.0.0.1", port=port, user="poc_admin",
                dbname="postgres", autocommit=True)
    # Only fixture creation bypasses protected Owners. Runtime transitions do not.
    with psycopg.connect(**conn) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized) VALUES (%s,'Outline Subject Fixture',"
                "'outline subject fixture')", (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) VALUES "
                "(%s,'OSUB186','osub186','Outline Subject Fixture',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,"
                "name,created_by) VALUES (%s,%s,'Outline Subject Fixture',%s)",
                (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_outline_versions("
                "solution_outline_version_id,solution_outline_id,project_id,"
                "version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,"
                "declared_requirement_count,declared_reference_count,created_by) "
                "VALUES (%s,%s,%s,1,%s,'[]'::jsonb,'[]'::jsonb,0,0,0,%s)",
                (version, outline, project, fingerprint, actor))
            db.execute(
                "INSERT INTO plm.sol_outline_version_create_results("
                "solution_outline_version_id,solution_outline_id,project_id,"
                "version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,"
                "declared_requirement_count,declared_reference_count,"
                "supersedes_version_ref,created_by,created_at) "
                "SELECT solution_outline_version_id,solution_outline_id,"
                "project_id,version_no,content_fingerprint,"
                "missing_declarations,conflict_declarations,"
                "declared_section_count,declared_requirement_count,"
                "declared_reference_count,supersedes_version_ref,"
                "created_by,created_at FROM plm.sol_outline_versions "
                "WHERE solution_outline_version_id=%s", (version,))
            db.execute(
                "INSERT INTO plm.rvw_reviews(review_id,scope,project_id,"
                "subject_type,subject_id,policy_code,review_state,"
                "active_round_id,created_by) VALUES "
                "(%s,'PROJECT',%s,'SOL-03',%s,"
                "'SOLUTION_OUTLINE_ALL_V1','IN_REVIEW',%s,%s)",
                (review, project, outline, round_id, actor))
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
                "(%s,%s,'PROJECT',%s,'SOL-03',%s,%s,%s,1,statement_timestamp())",
                (review, round_id, project, outline, version, fingerprint))
    runtime = create_database_runtime(url)
    repo = SqlAlchemyOutlineReviewSubjectRepository()
    try:
        # The first transaction deliberately aborts after a valid START write.
        try:
            with runtime.unit_of_work() as tx:
                locked = repo.lock_subject(
                    tx, project_id=project, outline_id=outline,
                    version_id=version)
                assert locked is not None and locked.latest_version_id == version
                assert repo.lock_subject(
                    tx, project_id=uuid.uuid4(), outline_id=outline,
                    version_id=version) is None
                repo.bind_start(tx, before=locked, review_id=review,
                                round_id=round_id, actor_id=actor)
                raise RuntimeError("intentional rollback")
        except RuntimeError as exc:
            assert str(exc) == "intentional rollback"
        with psycopg.connect(**conn) as db:
            assert db.execute(
                "SELECT version_state FROM plm.sol_outline_versions "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == "DRAFT"
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == 0
        with runtime.unit_of_work() as tx:
            locked = repo.lock_subject(
                tx, project_id=project, outline_id=outline,
                version_id=version)
            assert locked is not None
            repo.bind_start(tx, before=locked, review_id=review,
                            round_id=round_id, actor_id=actor)
            tx.commit()
        with psycopg.connect(**conn) as db:
            assert db.execute(
                "SELECT version_state,review_ref,review_round_ref "
                "FROM plm.sol_outline_versions WHERE "
                "solution_outline_version_id=%s", (version,)
            ).fetchone() == ("IN_REVIEW", review, round_id)
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s AND event_type='START'",
                (version,)).fetchone()[0] == 1
            # Review core terminal state is set by its own Owner in production.
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                           "active_round_id=NULL WHERE review_id=%s", (review,))
                db.execute("UPDATE plm.rvw_review_rounds "
                           "SET round_state='APPROVED' WHERE review_round_id=%s",
                           (round_id,))
                db.execute(
                    "INSERT INTO plm.rvw_round_events(review_id,review_round_id,"
                    "scope,project_id,event_type,actor_id,trace_id,occurred_at,"
                    "before_lock_version,after_lock_version,result_state) "
                    "VALUES (%s,%s,'PROJECT',%s,'COMPLETED',%s,%s,"
                    "statement_timestamp(),0,1,'APPROVED')",
                    (review, round_id, project, actor, uuid.uuid4()))
        transition = _transition(
            project=project, outline=outline, version=version, actor=actor,
            review=review, round_id=round_id, fingerprint=fingerprint)
        with runtime.unit_of_work() as tx:
            active = repo.lock_subject(
                tx, project_id=project, outline_id=outline,
                version_id=version)
            assert active is not None and active.version.version_state == "IN_REVIEW"
            result_id = repo.consume_terminal(
                tx, before=active, transition=transition,
                version_state="APPROVED")
            assert repo.assert_terminal_consumed(
                tx, transition=transition, version_state="APPROVED") == result_id
            tx.commit()
        with psycopg.connect(**conn) as db:
            assert db.execute(
                "SELECT current_approved_version_ref FROM plm.sol_outlines "
                "WHERE solution_outline_id=%s", (outline,)
            ).fetchone()[0] == version
            assert db.execute(
                "SELECT version_state FROM plm.sol_outline_versions "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == "APPROVED"
            assert db.execute(
                "SELECT count(*) FROM plm.sol_outline_review_state_results "
                "WHERE solution_outline_version_id=%s", (version,)
            ).fetchone()[0] == 2
    finally:
        runtime.dispose()
    print("SOL_03_A06_P04_P03_A02_OUTLINE_REVIEW_SUBJECT_PG_PASS")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
