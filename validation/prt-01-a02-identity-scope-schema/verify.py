"""Windows 11/PostgreSQL 18 proof for Prototype Schema0122."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261007_0121"


def connect(database: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    ))


def reject(operation, expected: str) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def create_database(prefix: str) -> str:
    database = prefix + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    return database


def drop_database(database: str) -> None:
    with connect("postgres") as admin:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
        )


def verify_existing_empty_and_drift() -> None:
    database = create_database("prt01a02empty_")
    try:
        cfg = config(database)
        command.upgrade(cfg, PREVIOUS)
        existing = uuid.uuid4()
        with connect(database) as db:
            db.execute(
                """
                INSERT INTO plm.auth_users(
                  user_id,username_display,username_normalized,state,deployment_role)
                VALUES (%s,'Existing actor','existing-prototype-actor',
                  'DISABLED','NONE')
                """,
                (existing,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (existing,)
            ).fetchone()[0] == 1
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='plm' AND table_name LIKE 'prt_%'"
                )
            }
            assert tables == {
                "prt_packages", "prt_prototypes", "prt_package_memberships",
                "prt_scope_decisions", "prt_scope_decision_requirement_refs",
            }, tables
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        drop_database(database)


def seed_dependency_graph(db) -> dict[str, uuid.UUID]:
    ids = {
        name: uuid.uuid4()
        for name in (
            "actor", "project", "other_project", "requirement", "requirement_version",
            "other_requirement", "other_requirement_version",
        )
    }
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            """
            INSERT INTO plm.auth_users(
              user_id,username_display,username_normalized,state,deployment_role)
            VALUES (%s,'Prototype schema actor','prototype-schema-actor',
              'DISABLED','NONE')
            """,
            (ids["actor"],),
        )
        db.execute(
            """
            INSERT INTO plm.prj_projects(
              project_id,project_code,project_code_normalized,name,created_by)
            VALUES (%s,'PRT001','prt001','Prototype schema',%s),
                   (%s,'PRT002','prt002','Other prototype schema',%s)
            """,
            (ids["project"], ids["actor"], ids["other_project"], ids["actor"]),
        )
        for project_key, requirement_key, version_key, code in (
            ("project", "requirement", "requirement_version", "PRT-REQ-1"),
            ("other_project", "other_requirement", "other_requirement_version", "PRT-REQ-2"),
        ):
            db.execute(
                """
                INSERT INTO plm.req_requirements(
                  requirement_id,project_id,requirement_code,
                  requirement_code_normalized,created_by)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (ids[requirement_key], ids[project_key], code, code, ids["actor"]),
            )
            db.execute(
                """
                INSERT INTO plm.req_requirement_versions(
                  requirement_version_id,requirement_id,project_id,version_no,
                  version_state,statement,rationale,domain_name,priority,risk,
                  requirement_classification,content_fingerprint,
                  declared_source_count,declared_acceptance_count,
                  declared_capability_count,declared_assumption_count,
                  declared_exclusion_count,declared_dependency_count,
                  declared_ai_task_count,created_by)
                VALUES (%s,%s,%s,1,'APPROVED','Synthetic statement',
                  'Synthetic rationale','Prototype','MEDIUM','LOW',
                  'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s)
                """,
                (
                    ids[version_key], ids[requirement_key], ids[project_key],
                    b"r" * 32, ids["actor"],
                ),
            )
    return ids


def verify_constraints_and_history() -> None:
    database = create_database("prt01a02data_")
    try:
        cfg = config(database)
        command.upgrade(cfg, "head")
        with connect(database) as db:
            ids = seed_dependency_graph(db)
            package_id, prototype_id = uuid.uuid4(), uuid.uuid4()
            db.execute(
                """
                INSERT INTO plm.prt_packages(
                  prototype_package_id,project_id,name,created_by)
                VALUES (%s,%s,'Implementation prototypes',%s)
                """,
                (package_id, ids["project"], ids["actor"]),
            )
            db.execute(
                """
                INSERT INTO plm.prt_prototypes(
                  prototype_id,project_id,name,created_by)
                VALUES (%s,%s,'Primary workflow prototype',%s)
                """,
                (prototype_id, ids["project"], ids["actor"]),
            )
            membership_id = uuid.uuid4()
            db.execute(
                """
                INSERT INTO plm.prt_package_memberships(
                  prototype_package_membership_id,prototype_package_id,
                  prototype_id,project_id,added_by)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (membership_id, package_id, prototype_id, ids["project"], ids["actor"]),
            )
            assert db.execute(
                """
                SELECT p.package_state,p.lock_version,r.prototype_state,
                       r.current_approved_version_ref,r.lock_version,m.project_id
                  FROM plm.prt_packages p
                  JOIN plm.prt_package_memberships m
                    ON m.prototype_package_id=p.prototype_package_id
                  JOIN plm.prt_prototypes r ON r.prototype_id=m.prototype_id
                 WHERE m.prototype_package_membership_id=%s
                """,
                (membership_id,),
            ).fetchone() == ("ACTIVE", 0, "ACTIVE", None, 0, ids["project"])

            other_prototype = uuid.uuid4()
            db.execute(
                """
                INSERT INTO plm.prt_prototypes(
                  prototype_id,project_id,name,created_by)
                VALUES (%s,%s,'Other project prototype',%s)
                """,
                (other_prototype, ids["other_project"], ids["actor"]),
            )
            reject(
                lambda: db.execute(
                    """
                    INSERT INTO plm.prt_package_memberships(
                      prototype_package_id,prototype_id,project_id,added_by)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (package_id, other_prototype, ids["project"], ids["actor"]),
                ),
                "fk_prt_package_memberships__prototype",
            )
            reject(
                lambda: db.execute(
                    """
                    INSERT INTO plm.prt_prototypes(
                      project_id,name,prototype_state,created_by)
                    VALUES (%s,'Invalid initial','NOT_REQUIRED',%s)
                    """,
                    (ids["project"], ids["actor"]),
                ),
                "Prototype initial state is invalid",
            )
            reject(
                lambda: db.execute(
                    """
                    INSERT INTO plm.prt_scope_decisions(
                      prototype_id,project_id,decision_type,reason,impact,
                      confirmed_by,before_version,after_version)
                    VALUES (%s,%s,'NOT_REQUIRED','Reason','Impact',%s,0,1)
                    """,
                    (prototype_id, ids["project"], ids["actor"]),
                ),
                "Prototype scope decision Owner is not installed",
            )

            decision_id = uuid.uuid4()
            db.execute("ALTER TABLE plm.prt_scope_decisions DISABLE TRIGGER USER")
            db.execute(
                """
                INSERT INTO plm.prt_scope_decisions(
                  scope_decision_id,prototype_id,project_id,decision_type,
                  reason,impact,confirmed_by,before_version,after_version)
                VALUES (%s,%s,%s,'NOT_REQUIRED','Synthetic reason',
                  'Synthetic impact',%s,0,1)
                """,
                (decision_id, prototype_id, ids["project"], ids["actor"]),
            )
            db.execute("ALTER TABLE plm.prt_scope_decisions ENABLE TRIGGER USER")
            db.execute(
                "ALTER TABLE plm.prt_scope_decision_requirement_refs "
                "DISABLE TRIGGER USER"
            )
            db.execute(
                """
                INSERT INTO plm.prt_scope_decision_requirement_refs(
                  scope_decision_id,prototype_id,project_id,requirement_id,
                  requirement_version_id,ordinal)
                VALUES (%s,%s,%s,%s,%s,1)
                """,
                (
                    decision_id, prototype_id, ids["project"], ids["requirement"],
                    ids["requirement_version"],
                ),
            )
            reject(
                lambda: db.execute(
                    """
                    INSERT INTO plm.prt_scope_decision_requirement_refs(
                      scope_decision_id,prototype_id,project_id,requirement_id,
                      requirement_version_id,ordinal)
                    VALUES (%s,%s,%s,%s,%s,2)
                    """,
                    (
                        decision_id, prototype_id, ids["project"],
                        ids["other_requirement"], ids["other_requirement_version"],
                    ),
                ),
                "fk_prt_scope_req_refs__requirement_version",
            )
            db.execute(
                "ALTER TABLE plm.prt_scope_decision_requirement_refs "
                "ENABLE TRIGGER USER"
            )
            reject(
                lambda: db.execute(
                    "UPDATE plm.prt_packages SET name='Changed' "
                    "WHERE prototype_package_id=%s",
                    (package_id,),
                ),
                "Prototype identity Owner is not installed",
            )
            reject(
                lambda: db.execute("TRUNCATE plm.prt_package_memberships"),
                "Prototype identity and scope history cannot be truncated",
            )
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Prototype identity or scope history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0122 accepted retained Prototype history")
    finally:
        drop_database(database)


def main() -> None:
    verify_existing_empty_and_drift()
    verify_constraints_and_history()
    print(
        "PRT_01_A02_IDENTITY_SCOPE_SCHEMA_PASS: Schema0122 existing/empty upgrade, "
        "empty downgrade/re-upgrade, drift, project-bound membership, fixed "
        "RequirementVersion scope, Owner closure and retained-history refusal "
        "verified on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
