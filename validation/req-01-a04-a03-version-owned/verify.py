"""Windows 11/PostgreSQL 18 proof for RequirementVersion owned collections."""

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
connect = helpers["connect"]
PREVIOUS = "20261007_0116"
TABLES = (
    "req_sources",
    "req_acceptance_criteria",
    "req_capability_assessments",
    "req_assumptions",
    "req_exclusions",
    "req_dependencies",
)


def reject(db, statement: str, params: tuple, sqlstate: str) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate == sqlstate, (error.sqlstate, str(error))
    else:
        raise AssertionError(f"operation unexpectedly succeeded: {statement}")


def main() -> None:
    database = "req01a04a03_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        actor, project, requirement, version = (uuid.uuid4() for _ in range(4))
        baseline, baseline_version, cap_row, cap_item = (
            uuid.uuid4() for _ in range(4)
        )
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.auth_users(user_id,username_display,"
                    "username_normalized,state,deployment_role) VALUES "
                    "(%s,'Requirement owner','requirement-owned','DISABLED','NONE')",
                    (actor,),
                )
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES "
                    "(%s,'REQOWN','reqown','Requirement owned project',%s)",
                    (project, actor),
                )
                db.execute(
                    "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                    "requirement_code,requirement_code_normalized,created_by) VALUES "
                    "(%s,%s,'REQ-OWNED','REQ-OWNED',%s)",
                    (requirement, project, actor),
                )
                db.execute(
                    "INSERT INTO plm.req_requirement_versions("
                    "requirement_version_id,requirement_id,project_id,version_no,"
                    "statement,rationale,domain_name,priority,risk,"
                    "requirement_classification,content_fingerprint,"
                    "declared_source_count,declared_acceptance_count,"
                    "declared_capability_count,declared_assumption_count,"
                    "declared_exclusion_count,declared_dependency_count,"
                    "declared_ai_task_count,created_by) VALUES "
                    "(%s,%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                    "'STANDARD_FUNCTION',%s,1,1,1,1,1,1,0,%s)",
                    (version, requirement, project, b"v" * 32, actor),
                )
                source_ref = "sha256:" + "a" * 64
                db.execute(
                    "INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,"
                    "baseline_state,source_collection_ref,current_approved_version_ref,"
                    "created_by) VALUES (%s,'REQ.OWNED','Requirement capability',"
                    "'ACTIVE',%s,%s,%s)",
                    (baseline, source_ref, baseline_version, actor),
                )
                db.execute(
                    "INSERT INTO plm.cap_baseline_versions(baseline_version_id,"
                    "baseline_id,version_no,version_state,source_collection_ref,"
                    "content_fingerprint,declared_item_count,declared_document_ref_count,"
                    "declared_evidence_ref_count,created_by) VALUES "
                    "(%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)",
                    (baseline_version, baseline, source_ref, b"c" * 32, actor),
                )
                db.execute(
                    "INSERT INTO plm.cap_items(capability_item_row_id,"
                    "baseline_version_id,baseline_id,capability_item_id,ordinal,"
                    "capability_code,domain_name,module_name,feature_name,name,"
                    "description,boundary_text,item_state) VALUES "
                    "(%s,%s,%s,%s,0,'REQ.OWNED.ITEM','PLM','Requirement','Owned',"
                    "'Owned capability','Capability description','Capability boundary',"
                    "'AVAILABLE')",
                    (cap_row, baseline_version, baseline, cap_item),
                )

            actual_tables = {
                row[0] for row in db.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='plm' AND table_name=ANY(%s)",
                    (list(TABLES),),
                )
            }
            assert actual_tables == set(TABLES), actual_tables
            for table in TABLES:
                trigger_names = {
                    row[0] for row in db.execute(
                        "SELECT tgname FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid "
                        "JOIN pg_namespace n ON n.oid=t.relnamespace "
                        "WHERE n.nspname='plm' AND t.relname=%s AND NOT g.tgisinternal",
                        (table,),
                    )
                }
                assert f"trg_{table}__owner" in trigger_names
                assert f"trg_{table}__no_truncate" in trigger_names

            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.req_assumptions(requirement_version_id,"
                        "requirement_id,project_id,ordinal,assumption_text) VALUES "
                        "(%s,%s,%s,0,'Direct write')",
                        (version, requirement, project),
                    )
            except psycopg.Error as error:
                assert "owned collection Owner is not installed" in str(error), str(error)
            else:
                raise AssertionError("closed owned collection accepted direct insert")

            try:
                with db.transaction():
                    db.execute("TRUNCATE plm.req_assumptions")
            except psycopg.Error as error:
                assert "owned collection history cannot be truncated" in str(error), str(error)
            else:
                raise AssertionError("owned collection accepted truncate")

            for table in TABLES:
                db.execute(
                    sql.SQL("ALTER TABLE plm.{} DISABLE TRIGGER {}").format(
                        sql.Identifier(table), sql.Identifier(f"trg_{table}__owner")
                    )
                )
                db.execute(
                    sql.SQL("ALTER TABLE plm.{} DISABLE TRIGGER {}").format(
                        sql.Identifier(table),
                        sql.Identifier(f"trg_{table}__completeness"),
                    )
                )
            try:
                survey = uuid.uuid4()
                source = db.execute(
                    "INSERT INTO plm.req_sources(requirement_version_id,requirement_id,"
                    "project_id,ordinal,source_type,source_object_id) VALUES "
                    "(%s,%s,%s,0,'APPROVED_SURVEY_CONCLUSION',%s) "
                    "RETURNING requirement_source_id",
                    (version, requirement, project, survey),
                ).fetchone()[0]
                criterion = db.execute(
                    "INSERT INTO plm.req_acceptance_criteria(requirement_version_id,"
                    "requirement_id,project_id,ordinal,observable_result,"
                    "verification_method,required_data,required_environment,"
                    "evidence_requirement) VALUES (%s,%s,%s,0,'Observable result',"
                    "'Execute acceptance test','Approved project fixture',"
                    "'Windows 11 test environment','Signed test evidence') "
                    "RETURNING acceptance_criterion_id",
                    (version, requirement, project),
                ).fetchone()[0]
                assessment = db.execute(
                    "INSERT INTO plm.req_capability_assessments("
                    "requirement_version_id,requirement_id,project_id,ordinal,"
                    "baseline_version_id,capability_item_id,match_type,fit_gap,"
                    "constraints_text,assessor_kind,assessed_by,assessed_at,"
                    "confirmation_state) VALUES (%s,%s,%s,0,%s,%s,'DIRECT',"
                    "'No functional gap','Approved baseline constraints','HUMAN',%s,"
                    "statement_timestamp(),'CONFIRMED') RETURNING capability_assessment_id",
                    (version, requirement, project, baseline_version, cap_item, actor),
                ).fetchone()[0]
                assumption = db.execute(
                    "INSERT INTO plm.req_assumptions(requirement_version_id,"
                    "requirement_id,project_id,ordinal,assumption_text) VALUES "
                    "(%s,%s,%s,0,'Customer supplies approved master data') "
                    "RETURNING requirement_assumption_id",
                    (version, requirement, project),
                ).fetchone()[0]
                exclusion = db.execute(
                    "INSERT INTO plm.req_exclusions(requirement_version_id,"
                    "requirement_id,project_id,ordinal,exclusion_text) VALUES "
                    "(%s,%s,%s,0,'Legacy data cleansing is excluded') "
                    "RETURNING requirement_exclusion_id",
                    (version, requirement, project),
                ).fetchone()[0]
                dependency = db.execute(
                    "INSERT INTO plm.req_dependencies(requirement_version_id,"
                    "requirement_id,project_id,ordinal,dependency_text) VALUES "
                    "(%s,%s,%s,0,'External ERP interface must be available') "
                    "RETURNING requirement_dependency_id",
                    (version, requirement, project),
                ).fetchone()[0]
                assert all((source, criterion, assessment, assumption, exclusion, dependency))

                reject(
                    db,
                    "INSERT INTO plm.req_sources(requirement_version_id,requirement_id,"
                    "project_id,ordinal,source_type,source_object_id) VALUES "
                    "(%s,%s,%s,1,'CONFIRMED_HANDOVER',%s)",
                    (version, requirement, project, uuid.uuid4()), "23514",
                )
                reject(
                    db,
                    "INSERT INTO plm.req_acceptance_criteria(requirement_version_id,"
                    "requirement_id,project_id,ordinal,observable_result,verification_method,"
                    "required_data,required_environment,evidence_requirement) VALUES "
                    "(%s,%s,%s,1,' ','Method','Data','Environment','Evidence')",
                    (version, requirement, project), "23514",
                )
                reject(
                    db,
                    "INSERT INTO plm.req_capability_assessments("
                    "requirement_version_id,requirement_id,project_id,ordinal,"
                    "baseline_version_id,capability_item_id,match_type,fit_gap,"
                    "constraints_text,assessor_kind,assessed_at,confirmation_state) VALUES "
                    "(%s,%s,%s,1,%s,%s,'DIRECT','No gap','Constraints',"
                    "'AI_CANDIDATE',statement_timestamp(),'CONFIRMED')",
                    (version, requirement, project, baseline_version, cap_item), "23514",
                )
                reject(
                    db,
                    "INSERT INTO plm.req_capability_assessments("
                    "requirement_version_id,requirement_id,project_id,ordinal,"
                    "baseline_version_id,capability_item_id,match_type,fit_gap,"
                    "constraints_text,assessor_kind,assessed_by,assessed_at,"
                    "confirmation_state) VALUES (%s,%s,%s,1,%s,%s,'UNKNOWN',"
                    "'Unknown gap','Unknown constraints','HUMAN',%s,"
                    "statement_timestamp(),'CANDIDATE')",
                    (version, requirement, project, baseline_version, uuid.uuid4(), actor),
                    "23503",
                )
                reject(
                    db,
                    "INSERT INTO plm.req_dependencies(requirement_version_id,"
                    "requirement_id,project_id,ordinal,dependency_text) VALUES "
                    "(%s,%s,%s,1,'Wrong project')",
                    (version, requirement, uuid.uuid4()), "23503",
                )
                reject(
                    db,
                    "INSERT INTO plm.req_assumptions(requirement_version_id,"
                    "requirement_id,project_id,ordinal,assumption_text) VALUES "
                    "(%s,%s,%s,0,'Duplicate ordinal')",
                    (version, requirement, project), "23505",
                )
            finally:
                for table in TABLES:
                    db.execute(
                        sql.SQL("ALTER TABLE plm.{} ENABLE TRIGGER {}").format(
                            sql.Identifier(table),
                            sql.Identifier(f"trg_{table}__completeness"),
                        )
                    )
                    db.execute(
                        sql.SQL("ALTER TABLE plm.{} ENABLE TRIGGER {}").format(
                            sql.Identifier(table), sql.Identifier(f"trg_{table}__owner")
                        )
                    )
            assert all(
                db.execute(sql.SQL("SELECT count(*) FROM plm.{}").format(
                    sql.Identifier(table))).fetchone()[0] == 1
                for table in TABLES
            )
            try:
                with db.transaction():
                    db.execute(
                        "UPDATE plm.req_assumptions SET assumption_text='Changed' "
                        "WHERE requirement_assumption_id=%s", (assumption,),
                    )
            except psycopg.Error as error:
                assert "owned collection Owner is not installed" in str(error), str(error)
            else:
                raise AssertionError("closed owned collection accepted update")

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "RequirementVersion owned history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0117 accepted owned history")
        print(
            "REQ_01_A04_A03_VERSION_OWNED_PASS: six ordered owned tables, exact "
            "capability FK, source/acceptance/assessment shapes, cross-project and "
            "duplicate rejection, closed Owner, truncate protection and history "
            "downgrade refusal verified on PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
