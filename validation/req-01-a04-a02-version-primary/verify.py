"""Windows 11/PostgreSQL 18 proof for RequirementVersion primary schema."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(
    str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py")
)
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261007_0115"


def main() -> None:
    database = "req01a04a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg",
            username="poc_admin",
            host="127.0.0.1",
            port=55434,
            database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        with connect(database) as db:
            creator = seed_user(db, "Requirement Version Creator", "NONE", b"v" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('REQV01','reqv01','Requirement Version Project',%s) "
                "RETURNING project_id",
                (creator,),
            ).fetchone()[0]
            requirement = db.execute(
                "INSERT INTO plm.req_requirements(project_id,requirement_code,"
                "requirement_code_normalized,created_by) VALUES (%s,'REQ-VERSION',"
                "'REQ-VERSION',%s) RETURNING requirement_id",
                (project, creator),
            ).fetchone()[0]

            columns = {
                row[0]: (row[1], row[2])
                for row in db.execute(
                    "SELECT column_name,is_nullable,data_type FROM information_schema.columns "
                    "WHERE table_schema='plm' AND table_name='req_requirement_versions'"
                )
            }
            required = {
                "requirement_version_id",
                "requirement_id",
                "project_id",
                "version_no",
                "version_state",
                "statement",
                "rationale",
                "domain_name",
                "priority",
                "risk",
                "requirement_classification",
                "content_fingerprint",
                "declared_source_count",
                "declared_acceptance_count",
                "declared_capability_count",
                "declared_assumption_count",
                "declared_exclusion_count",
                "declared_dependency_count",
                "declared_ai_task_count",
                "created_by",
                "created_at",
            }
            assert required <= columns.keys(), required - columns.keys()
            assert columns["title"][0] == "YES"
            assert all(columns[name][0] == "NO" for name in required)

            constraints = {
                row[0]: (row[1], row[2])
                for row in db.execute(
                    "SELECT conname,contype,convalidated FROM pg_constraint c "
                    "JOIN pg_class t ON t.oid=c.conrelid "
                    "JOIN pg_namespace n ON n.oid=t.relnamespace "
                    "WHERE n.nspname='plm' AND t.relname IN "
                    "('req_requirement_versions','req_requirements')"
                )
            }
            expected_constraints = {
                "uq_req_versions__id_requirement_project",
                "uq_req_versions__requirement_no",
                "fk_req_versions__requirement",
                "fk_req_versions__supersedes",
                "fk_req_versions__review",
                "fk_req_versions__round",
                "fk_req_versions__creator",
                "fk_req_requirements__approved_version",
                "ck_req_versions__number",
                "ck_req_versions__state",
                "ck_req_versions__fingerprint",
                "ck_req_versions__counts",
                "ck_req_versions__supersedes_not_self",
            }
            assert expected_constraints <= constraints.keys(), (
                expected_constraints - constraints.keys()
            )
            assert all(constraints[name][1] for name in expected_constraints)

            indexes = {
                row[0]: row[1]
                for row in db.execute(
                    "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='plm' "
                    "AND tablename='req_requirement_versions'"
                )
            }
            for name in (
                "ix_req_versions__requirement_created",
                "uq_req_versions__requirement_in_review",
                "uq_req_versions__requirement_approved",
            ):
                assert name in indexes, name
            assert "UNIQUE" in indexes["uq_req_versions__requirement_in_review"]
            assert "version_state = 'IN_REVIEW'" in indexes[
                "uq_req_versions__requirement_in_review"
            ]

            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.req_requirement_versions(requirement_id,project_id,"
                        "version_no,statement,rationale,domain_name,priority,risk,"
                        "requirement_classification,content_fingerprint,declared_source_count,"
                        "declared_acceptance_count,declared_capability_count,"
                        "declared_assumption_count,declared_exclusion_count,"
                        "declared_dependency_count,declared_ai_task_count,created_by) VALUES "
                        "(%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                        "'STANDARD_FUNCTION',%s,1,0,0,0,0,0,0,%s)",
                        (requirement, project, b"a" * 32, creator),
                    )
            except psycopg.Error as error:
                assert "RequirementVersion Owner is not installed" in str(error), str(error)
            else:
                raise AssertionError("direct RequirementVersion insert was accepted")

            try:
                with db.transaction():
                    db.execute("TRUNCATE plm.req_requirement_versions CASCADE")
            except psycopg.Error as error:
                assert "RequirementVersion history cannot be truncated" in str(error), str(error)
            else:
                raise AssertionError("RequirementVersion truncate was accepted")

            db.execute(
                "ALTER TABLE plm.req_requirement_versions DISABLE TRIGGER "
                "trg_req_requirement_versions__owner"
            )
            db.execute(
                "ALTER TABLE plm.req_requirement_versions DISABLE TRIGGER "
                "trg_req_requirement_versions__completeness"
            )
            try:
                self_ref = uuid.uuid4()
                try:
                    with db.transaction():
                        db.execute(
                            "INSERT INTO plm.req_requirement_versions("
                            "requirement_version_id,requirement_id,project_id,version_no,"
                            "statement,rationale,domain_name,priority,risk,"
                            "requirement_classification,content_fingerprint,"
                            "declared_source_count,declared_acceptance_count,"
                            "declared_capability_count,declared_assumption_count,"
                            "declared_exclusion_count,declared_dependency_count,"
                            "declared_ai_task_count,supersedes_version_ref,created_by) VALUES "
                            "(%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                            "'STANDARD_FUNCTION',%s,1,0,0,0,0,0,0,%s,%s)",
                            (self_ref, requirement, project, b"s" * 32, self_ref, creator),
                        )
                except psycopg.Error as error:
                    assert error.sqlstate == "23514", str(error)
                else:
                    raise AssertionError("self-superseding RequirementVersion was accepted")
                version = db.execute(
                    "INSERT INTO plm.req_requirement_versions(requirement_id,project_id,"
                    "version_no,version_state,title,statement,rationale,domain_name,priority,"
                    "risk,requirement_classification,content_fingerprint,declared_source_count,"
                    "declared_acceptance_count,declared_capability_count,"
                    "declared_assumption_count,declared_exclusion_count,"
                    "declared_dependency_count,declared_ai_task_count,created_by) VALUES "
                    "(%s,%s,1,'DRAFT',NULL,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                    "'STANDARD_FUNCTION',%s,1,0,0,0,0,0,0,%s) "
                    "RETURNING requirement_version_id",
                    (requirement, project, b"b" * 32, creator),
                ).fetchone()[0]
            finally:
                db.execute(
                    "ALTER TABLE plm.req_requirement_versions ENABLE TRIGGER "
                    "trg_req_requirement_versions__completeness"
                )
                db.execute(
                    "ALTER TABLE plm.req_requirement_versions ENABLE TRIGGER "
                    "trg_req_requirement_versions__owner"
                )
            assert version

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "RequirementVersion history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0116 accepted RequirementVersion history")
        print(
            "REQ_01_A04_A02_VERSION_PRIMARY_PASS: empty-history upgrade/downgrade, "
            "drift, primary fields, approved pointer FK, state indexes, closed Owner, "
            "truncate protection and history downgrade refusal verified on PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )


if __name__ == "__main__":
    main()
