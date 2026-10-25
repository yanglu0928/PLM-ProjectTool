"""Windows 11/PostgreSQL 18 proof for RequirementPrototypeLink Schema0134."""

from __future__ import annotations

import json
import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261008_0133"


def expect_database(message: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + message)


def coverage(covered: uuid.UUID, *, reason: str | None = None) -> dict[str, object]:
    return {
        "covered_acceptance_criterion_refs": [str(covered)],
        "uncovered_acceptance_criteria": (
            [] if reason is None else [{
                "acceptance_criterion_ref": str(uuid.uuid4()),
                "reason": reason,
            }]
        ),
    }


def insert_link(
    db, link_id: uuid.UUID, project_id: uuid.UUID,
    requirement_id: uuid.UUID, requirement_version_id: uuid.UUID,
    prototype_id: uuid.UUID, prototype_version_id: uuid.UUID,
    actor_id: uuid.UUID, purpose: str, payload: dict[str, object],
) -> None:
    db.execute(
        "INSERT INTO plm.prt_requirement_links("
        "requirement_prototype_link_id,project_id,requirement_id,"
        "requirement_version_id,prototype_id,prototype_version_id,purpose,"
        "coverage_schema_version,coverage,created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s)",
        (link_id, project_id, requirement_id, requirement_version_id,
         prototype_id, prototype_version_id, purpose, Jsonb(payload), actor_id),
    )


def main() -> None:
    database = "prt01a08a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        with connect(database) as db:
            actor = seed_user(db, "PRT Link schema actor", "NONE", b"l" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('PRTL01','prtl01','Link schema project',%s) "
                "RETURNING project_id", (actor,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('PRTL02','prtl02','Other link project',%s) "
                "RETURNING project_id", (actor,),
            ).fetchone()[0]
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        requirement_id, requirement_version_id = uuid.uuid4(), uuid.uuid4()
        prototype_id, prototype_version_id = uuid.uuid4(), uuid.uuid4()
        criterion = uuid.uuid4()
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.req_requirement_versions("
                    "requirement_version_id,requirement_id,project_id,version_no,"
                    "version_state,statement,rationale,domain_name,priority,risk,"
                    "requirement_classification,content_fingerprint,"
                    "declared_source_count,declared_acceptance_count,"
                    "declared_capability_count,declared_assumption_count,"
                    "declared_exclusion_count,declared_dependency_count,"
                    "declared_ai_task_count,created_by) VALUES ("
                    "%s,%s,%s,1,'APPROVED','s','r','d','HIGH','HIGH',"
                    "'STANDARD_FUNCTION',%s,1,1,0,0,0,0,0,%s)",
                    (requirement_version_id, requirement_id, project,
                     b"r" * 32, actor),
                )
                db.execute(
                    "INSERT INTO plm.prt_prototype_versions("
                    "prototype_version_id,prototype_id,project_id,version_no,"
                    "version_state,template_ref,template_version_ref,coverage_summary,"
                    "content_fingerprint,declared_artifact_count,"
                    "declared_requirement_count,declared_interaction_count,created_by) "
                    "VALUES (%s,%s,%s,1,'APPROVED',%s,%s,'{}',%s,1,1,1,%s)",
                    (prototype_version_id, prototype_id, project, uuid.uuid4(),
                     uuid.uuid4(), b"p" * 32, actor),
                )

            first = uuid.uuid4()
            insert_link(
                db, first, project, requirement_id, requirement_version_id,
                prototype_id, prototype_version_id, actor, "ILLUSTRATES",
                coverage(criterion),
            )

            expect_database(
                "ck_prt_requirement_links__purpose",
                lambda: insert_link(
                    db, uuid.uuid4(), project, requirement_id,
                    requirement_version_id, uuid.uuid4(), prototype_version_id,
                    actor, "UNKNOWN", coverage(criterion),
                ),
            )
            expect_database(
                "ck_prt_requirement_links__coverage",
                lambda: insert_link(
                    db, uuid.uuid4(), project, requirement_id,
                    requirement_version_id, uuid.uuid4(), prototype_version_id,
                    actor, "VALIDATES", {
                        "covered_acceptance_criterion_refs": [],
                        "uncovered_acceptance_criteria": [],
                    },
                ),
            )
            expect_database(
                "fk_prt_requirement_links__requirement_version",
                lambda: insert_link(
                    db, uuid.uuid4(), other_project, requirement_id,
                    requirement_version_id, prototype_id, prototype_version_id,
                    actor, "VALIDATES", coverage(criterion),
                ),
            )
            expect_database(
                "uq_prt_requirement_links__active_identity_purpose",
                lambda: insert_link(
                    db, uuid.uuid4(), project, requirement_id,
                    requirement_version_id, prototype_id, prototype_version_id,
                    actor, "ILLUSTRATES", coverage(criterion, reason="gap"),
                ),
            )
            expect_database(
                "RequirementPrototypeLink lifecycle mutation is invalid",
                lambda: db.execute(
                    "UPDATE plm.prt_requirement_links SET purpose='VALIDATES' "
                    "WHERE requirement_prototype_link_id=%s", (first,),
                ),
            )

            revoked = uuid.uuid4()
            insert_link(
                db, revoked, project, requirement_id, requirement_version_id,
                prototype_id, prototype_version_id, actor, "VALIDATES",
                coverage(criterion),
            )
            db.execute(
                "UPDATE plm.prt_requirement_links SET link_state='REVOKED',"
                "lock_version=1 WHERE requirement_prototype_link_id=%s", (revoked,),
            )
            expect_database(
                "RequirementPrototypeLink lifecycle mutation is invalid",
                lambda: db.execute(
                    "UPDATE plm.prt_requirement_links SET link_state='ACTIVE',"
                    "lock_version=0 WHERE requirement_prototype_link_id=%s", (revoked,),
                ),
            )

            unchanged = uuid.uuid4()
            insert_link(
                db, unchanged, project, requirement_id, requirement_version_id,
                prototype_id, prototype_version_id, actor,
                "ACCEPTANCE_REFERENCE", coverage(criterion),
            )

            def identical_replacement() -> None:
                candidate = uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "UPDATE plm.prt_requirement_links SET "
                        "link_state='SUPERSEDED',lock_version=1,"
                        "superseded_by_ref=%s WHERE "
                        "requirement_prototype_link_id=%s", (candidate, unchanged),
                    )
                    insert_link(
                        db, candidate, project, requirement_id,
                        requirement_version_id, prototype_id,
                        prototype_version_id, actor, "ACCEPTANCE_REFERENCE",
                        coverage(criterion),
                    )

            expect_database(
                "RequirementPrototypeLink replacement is invalid",
                identical_replacement,
            )
            assert db.execute(
                "SELECT link_state FROM plm.prt_requirement_links WHERE "
                "requirement_prototype_link_id=%s", (unchanged,),
            ).fetchone()[0] == "ACTIVE"

            replacement = uuid.uuid4()
            with db.transaction():
                db.execute(
                    "UPDATE plm.prt_requirement_links SET link_state='SUPERSEDED',"
                    "lock_version=1,superseded_by_ref=%s "
                    "WHERE requirement_prototype_link_id=%s", (replacement, first),
                )
                insert_link(
                    db, replacement, project, requirement_id,
                    requirement_version_id, prototype_id, prototype_version_id,
                    actor, "ILLUSTRATES", coverage(criterion, reason="bounded gap"),
                )
            state = db.execute(
                "SELECT link_state,superseded_by_ref FROM plm.prt_requirement_links "
                "WHERE requirement_prototype_link_id=%s", (first,),
            ).fetchone()
            assert state == ("SUPERSEDED", replacement), state
            assert db.execute(
                "SELECT count(*) FROM plm.prt_requirement_links WHERE "
                "project_id=%s AND requirement_id=%s AND prototype_id=%s AND "
                "purpose='ILLUSTRATES' AND link_state='ACTIVE'",
                (project, requirement_id, prototype_id),
            ).fetchone()[0] == 1

            expect_database(
                "RequirementPrototypeLink history is immutable",
                lambda: db.execute(
                    "DELETE FROM plm.prt_requirement_links WHERE "
                    "requirement_prototype_link_id=%s", (replacement,),
                ),
            )
            expect_database(
                "RequirementPrototypeLink history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.prt_requirement_links"),
            )
            assert json.loads(db.execute(
                "SELECT coverage::text FROM plm.prt_requirement_links WHERE "
                "requirement_prototype_link_id=%s", (replacement,),
            ).fetchone()[0])["uncovered_acceptance_criteria"][0]["reason"] == "bounded gap"

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "RequirementPrototypeLink history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0134 accepted Link history downgrade")
        print(
            "PRT_01_A08_A02_LINK_SCHEMA_PASS: existing-data upgrade, empty "
            "downgrade/re-upgrade, drift, composite endpoints, coverage/purpose, "
            "ACTIVE uniqueness, irreversible revoke/supersede, replacement closure, "
            "truncate/delete rejection and history downgrade refusal verified on "
            "PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )


if __name__ == "__main__":
    main()
