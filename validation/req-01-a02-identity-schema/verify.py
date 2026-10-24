"""Windows 11/PostgreSQL 18 proof for Schema0111 Requirement identity."""

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
PREVIOUS = "20261007_0110"


def connect(database: str):
    return psycopg.connect(
        host=HOST,
        port=PORT,
        user=USER,
        dbname=database,
        autocommit=True,
        connect_timeout=5,
    )


def config(database: str):
    return create_migration_config(
        URL.create(
            "postgresql+psycopg",
            username=USER,
            host=HOST,
            port=PORT,
            database=database,
        )
    )


def reject(operation, expected: str) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def seed_dependencies(db) -> dict[str, uuid.UUID]:
    ids = {name: uuid.uuid4() for name in ("actor", "project", "other_project")}
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            """
            INSERT INTO plm.auth_users(
              user_id,username_display,username_normalized,state,deployment_role)
            VALUES (%s,'Requirement schema actor','requirement-schema-actor',
              'DISABLED','NONE')
            """,
            (ids["actor"],),
        )
        db.execute(
            """
            INSERT INTO plm.prj_projects(
              project_id,project_code,project_code_normalized,name,created_by)
            VALUES (%s,'REQ001','req001','Requirement schema',%s),
                   (%s,'REQ002','req002','Other requirement schema',%s)
            """,
            (ids["project"], ids["actor"], ids["other_project"], ids["actor"]),
        )
    return ids


def insert_package(db, ids, *, project: uuid.UUID | None = None) -> uuid.UUID:
    package_id = uuid.uuid4()
    db.execute(
        """
        INSERT INTO plm.req_packages(
          requirement_package_id,project_id,name,created_by)
        VALUES (%s,%s,'Implementation scope',%s)
        """,
        (package_id, project or ids["project"], ids["actor"]),
    )
    return package_id


def insert_requirement(
    db,
    ids,
    *,
    code: str,
    project: uuid.UUID | None = None,
    normalized: str | None = None,
) -> uuid.UUID:
    requirement_id = uuid.uuid4()
    db.execute(
        """
        INSERT INTO plm.req_requirements(
          requirement_id,project_id,requirement_code,
          requirement_code_normalized,created_by)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            requirement_id,
            project or ids["project"],
            code,
            normalized or code.upper(),
            ids["actor"],
        ),
    )
    return requirement_id


def insert_membership(db, ids, package_id, requirement_id, project) -> uuid.UUID:
    membership_id = uuid.uuid4()
    db.execute(
        """
        INSERT INTO plm.req_package_memberships(
          requirement_package_membership_id,requirement_package_id,
          requirement_id,project_id,added_by)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (membership_id, package_id, requirement_id, project, ids["actor"]),
    )
    return membership_id


def verify_empty_existing_and_drift() -> None:
    database = "req01a02empty_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        cfg = config(database)
        command.upgrade(cfg, PREVIOUS)
        existing = uuid.uuid4()
        with connect(database) as db:
            db.execute(
                """
                INSERT INTO plm.auth_users(
                  user_id,username_display,username_normalized,state,deployment_role)
                VALUES (%s,'Existing actor','existing-requirement-actor',
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
                    "WHERE table_schema='plm' AND table_name LIKE 'req_%'"
                )
            }
            assert tables == {
                "req_packages",
                "req_requirements",
                "req_package_memberships",
            }, tables
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )


def verify_constraints_and_retained_history() -> None:
    database = "req01a02data_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        cfg = config(database)
        command.upgrade(cfg, "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
            package_id = insert_package(db, ids)
            requirement_id = insert_requirement(db, ids, code="REQ-001")
            membership_id = insert_membership(
                db, ids, package_id, requirement_id, ids["project"]
            )
            row = db.execute(
                """
                SELECT p.package_state,p.lock_version,r.requirement_state,
                       r.current_approved_version_ref,r.lock_version,
                       m.project_id
                  FROM plm.req_packages p
                  JOIN plm.req_package_memberships m
                    ON m.requirement_package_id=p.requirement_package_id
                  JOIN plm.req_requirements r
                    ON r.requirement_id=m.requirement_id
                 WHERE m.requirement_package_membership_id=%s
                """,
                (membership_id,),
            ).fetchone()
            assert row == ("ACTIVE", 0, "ACTIVE", None, 0, ids["project"]), row

            reject(
                lambda: insert_requirement(db, ids, code="req-001"),
                "uq_req_requirements__project_code",
            )
            reject(
                lambda: insert_requirement(
                    db, ids, code="REQ-002", normalized="not-normalized"
                ),
                "ck_req_requirements__code_normalized",
            )
            other_requirement = insert_requirement(
                db, ids, code="REQ-OTHER", project=ids["other_project"]
            )
            reject(
                lambda: insert_membership(
                    db, ids, package_id, other_requirement, ids["project"]
                ),
                "fk_req_package_memberships__requirement",
            )
            reject(
                lambda: insert_membership(
                    db, ids, package_id, requirement_id, ids["project"]
                ),
                "uq_req_package_memberships__package_requirement",
            )
            reject(
                lambda: db.execute(
                    """
                    INSERT INTO plm.req_requirements(
                      project_id,requirement_code,requirement_code_normalized,
                      current_approved_version_ref,created_by)
                    VALUES (%s,'REQ-POINTER','REQ-POINTER',%s,%s)
                    """,
                    (ids["project"], uuid.uuid4(), ids["actor"]),
                ),
                "Requirement initial state is invalid",
            )
            reject(
                lambda: db.execute(
                    "UPDATE plm.req_packages SET name='Changed' "
                    "WHERE requirement_package_id=%s",
                    (package_id,),
                ),
                "Requirement identity Owner is not installed",
            )
            reject(
                lambda: db.execute(
                    "DELETE FROM plm.req_package_memberships "
                    "WHERE requirement_package_membership_id=%s",
                    (membership_id,),
                ),
                "Requirement identity Owner is not installed",
            )
            reject(
                lambda: db.execute("TRUNCATE plm.req_package_memberships"),
                "Requirement identity history cannot be truncated",
            )
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Requirement identity history prevents downgrade" in str(error), str(
                error
            )
        else:
            raise AssertionError("Schema0111 accepted retained Requirement history")
    finally:
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database)
                )
            )


def main() -> None:
    verify_empty_existing_and_drift()
    verify_constraints_and_retained_history()
    print(
        "REQ_01_A02_IDENTITY_SCHEMA_PASS: Schema0111 existing/empty upgrade, "
        "empty downgrade/re-upgrade, drift, normalized project code, same-project "
        "membership, owner closure and retained-history refusal verified on "
        "PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
