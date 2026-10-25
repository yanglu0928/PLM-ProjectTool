"""Windows 11/PostgreSQL 18.6 proof for Requirement scope locks."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.requirement.infrastructure.workflow_qualification_repository import (
    SqlAlchemyRequirementWorkflowQualificationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(
    ROOT / "validation" / "req-01-a08-a02-p02-review-owner" / "verify.py"
))
connect = base["connect"]
seed_dependencies = base["seed_dependencies"]


def insert_scope(db, ids):
    project, actor = ids["project"], ids["actor"]
    active = sorted((uuid.uuid4(), uuid.uuid4()), key=lambda value: value.int)
    deferred, archived = uuid.uuid4(), uuid.uuid4()
    versions = {value: uuid.uuid4() for value in active}
    reviews = {value: (uuid.uuid4(), uuid.uuid4()) for value in active}
    decisions = {deferred: uuid.uuid4(), archived: uuid.uuid4()}
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        for index, requirement_id in enumerate(active, 1):
            version_id = versions[requirement_id]
            review_id, round_id = reviews[requirement_id]
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                "requirement_code,requirement_code_normalized,requirement_state,"
                "current_approved_version_ref,created_by,lock_version) VALUES "
                "(%s,%s,%s,%s,'ACTIVE',%s,%s,2)",
                (requirement_id, project, f"REQ-SCOPE-{index}",
                 f"REQ-SCOPE-{index}", version_id, actor),
            )
            db.execute(
                "INSERT INTO plm.req_requirement_versions("
                "requirement_version_id,requirement_id,project_id,version_no,"
                "version_state,title,statement,rationale,domain_name,priority,risk,"
                "requirement_classification,content_fingerprint,"
                "declared_source_count,declared_acceptance_count,"
                "declared_capability_count,declared_assumption_count,"
                "declared_exclusion_count,declared_dependency_count,"
                "declared_ai_task_count,review_ref,review_round_ref,created_by) "
                "VALUES (%s,%s,%s,1,'APPROVED',%s,'Observable statement',"
                "'Business rationale','PLM','HIGH','MEDIUM','STANDARD_FUNCTION',"
                "%s,1,1,1,0,0,0,0,%s,%s,%s)",
                (version_id, requirement_id, project, f"Scope {index}",
                 version_id.bytes + version_id.bytes,
                 review_id, round_id, actor),
            )
        for requirement_id, state, decision_type, lock_version in (
            (deferred, "DEFERRED", "DEFER", 1),
            (archived, "ARCHIVED", "REJECT", 2),
        ):
            decision_id = decisions[requirement_id]
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                "requirement_code,requirement_code_normalized,requirement_state,"
                "current_approved_version_ref,created_by,lock_version) VALUES "
                "(%s,%s,%s,%s,%s,NULL,%s,%s)",
                (requirement_id, project, f"REQ-{state}", f"REQ-{state}",
                 state, actor, lock_version),
            )
            db.execute(
                "INSERT INTO plm.req_requirement_state_decisions("
                "decision_id,requirement_id,project_id,decision_type,reason,impact,"
                "decided_by,before_version,after_version) VALUES "
                "(%s,%s,%s,%s,'Scope decision','Delivery impact',%s,0,1)",
                (decision_id, requirement_id, project, decision_type, actor),
            )
    return {
        "active": tuple(active), "deferred": deferred, "archived": archived,
        "versions": versions, "reviews": reviews, "decisions": decisions,
    }


def expect_locked(database, table, identity, value):
    with connect(database) as rival:
        try:
            rival.execute(sql.SQL(
                "SELECT 1 FROM plm.{} WHERE {}=%s FOR UPDATE NOWAIT"
            ).format(sql.Identifier(table), sql.Identifier(identity)), (value,))
        except Exception as error:
            assert getattr(error, "sqlstate", None) == "55P03", (
                table, getattr(error, "sqlstate", None),
            )
            rival.rollback()
        else:
            raise AssertionError(f"qualification did not lock {table}")


def main() -> None:
    database = "req01a12a03a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database),
        ))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            scope = insert_scope(db, ids)
        runtime = create_database_runtime(url)
        repository = SqlAlchemyRequirementWorkflowQualificationRepository()

        with runtime.unit_of_work() as tx:
            locked = repository.lock_complete_scope(
                tx, project_id=ids["project"],
            )
            assert locked is not None
            assert locked.root_count == 4
            assert tuple(
                value.snapshot.requirement_id for value in locked.approved
            ) == scope["active"]
            assert tuple(
                value.snapshot.requirement_version_id for value in locked.approved
            ) == tuple(scope["versions"][value] for value in scope["active"])
            assert {value.requirement_state for value in locked.decisions} == {
                "DEFERRED", "ARCHIVED",
            }
            first = scope["active"][0]
            expect_locked(database, "prj_projects", "project_id", ids["project"])
            expect_locked(database, "req_requirements", "requirement_id", first)
            expect_locked(
                database, "req_requirement_versions", "requirement_version_id",
                scope["versions"][first],
            )
            expect_locked(
                database, "req_requirement_state_decisions", "decision_id",
                scope["decisions"][scope["deferred"]],
            )

        with connect(database) as db:
            empty_project = uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES "
                    "(%s,'EMPTY-SCOPE','EMPTY-SCOPE','Empty scope',%s)",
                    (empty_project, ids["actor"]),
                )
        with runtime.unit_of_work() as tx:
            assert repository.lock_complete_scope(
                tx, project_id=empty_project,
            ) is None

        first = scope["active"][0]
        draft = uuid.uuid4()
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.req_requirement_versions("
                "requirement_version_id,requirement_id,project_id,version_no,"
                "version_state,title,statement,rationale,domain_name,priority,risk,"
                "requirement_classification,content_fingerprint,"
                "declared_source_count,declared_acceptance_count,"
                "declared_capability_count,declared_assumption_count,"
                "declared_exclusion_count,declared_dependency_count,"
                "declared_ai_task_count,created_by) VALUES "
                "(%s,%s,%s,2,'DRAFT','Pending revision','Pending statement',"
                "'Pending rationale','PLM','HIGH','MEDIUM','STANDARD_FUNCTION',"
                "%s,1,1,1,0,0,0,0,%s)",
                (draft, first, ids["project"], draft.bytes + draft.bytes,
                 ids["actor"]),
            )
        with runtime.unit_of_work() as tx:
            assert repository.lock_complete_scope(
                tx, project_id=ids["project"],
            ) is None
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "DELETE FROM plm.req_requirement_versions WHERE "
                "requirement_version_id=%s", (draft,),
            )

        direct_archive = uuid.uuid4()
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                "requirement_code,requirement_code_normalized,requirement_state,"
                "current_approved_version_ref,created_by,lock_version) VALUES "
                "(%s,%s,'REQ-DIRECT-ARCHIVE','REQ-DIRECT-ARCHIVE','ARCHIVED',"
                "NULL,%s,1)",
                (direct_archive, ids["project"], ids["actor"]),
            )
        with runtime.unit_of_work() as tx:
            assert repository.lock_complete_scope(
                tx, project_id=ids["project"],
            ) is None
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "DELETE FROM plm.req_requirements WHERE requirement_id=%s",
                (direct_archive,),
            )

        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.req_requirements SET lock_version=3 WHERE "
                "requirement_id=%s", (scope["archived"],),
            )
        with runtime.unit_of_work() as tx:
            assert repository.lock_complete_scope(
                tx, project_id=ids["project"],
            ) is None
        with connect(database) as db, db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "UPDATE plm.req_requirements SET lock_version=2 WHERE "
                "requirement_id=%s", (scope["archived"],),
            )

        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(sql.SQL(
                "DROP DATABASE IF EXISTS {} WITH (FORCE)"
            ).format(sql.Identifier(database)))
    print(
        "REQ_01_A12_A03_A02_WORKFLOW_SCOPE_PG_PASS: Windows 11/PostgreSQL "
        "18.6 complete Requirement root scope, canonical two-approved-version "
        "set, DEFER/ARCHIVE decisions, project/root/version/decision locks, "
        "empty/pending/direct-archive/decision-drift fail-closed and Alembic "
        "drift verified"
    )


if __name__ == "__main__":
    main()
