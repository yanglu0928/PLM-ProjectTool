"""Windows 11/PostgreSQL 18 proof for RequirementVersion support closure."""

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
PREVIOUS = "20261007_0117"
OWNER_TABLES = (
    "req_requirement_versions",
    "req_sources",
    "req_acceptance_criteria",
    "req_capability_assessments",
    "req_assumptions",
    "req_exclusions",
    "req_dependencies",
    "req_source_evidence_refs",
    "req_assessment_evidence_refs",
    "req_version_ai_task_refs",
)


def set_owner_triggers(db, enabled: bool) -> None:
    action = "ENABLE" if enabled else "DISABLE"
    for table in OWNER_TABLES:
        db.execute(
            sql.SQL("ALTER TABLE plm.{} {} TRIGGER {}").format(
                sql.Identifier(table), sql.SQL(action),
                sql.Identifier(f"trg_{table}__owner"),
            )
        )


def insert_version(db, ids: dict, version: uuid.UUID, version_no: int, *,
                   sources: int = 1, acceptance: int = 0, capability: int = 0,
                   assumptions: int = 0, exclusions: int = 0,
                   dependencies: int = 0, ai_tasks: int = 0) -> None:
    db.execute(
        "INSERT INTO plm.req_requirement_versions(requirement_version_id,"
        "requirement_id,project_id,version_no,statement,rationale,domain_name,"
        "priority,risk,requirement_classification,content_fingerprint,"
        "declared_source_count,declared_acceptance_count,"
        "declared_capability_count,declared_assumption_count,"
        "declared_exclusion_count,declared_dependency_count,"
        "declared_ai_task_count,created_by) VALUES "
        "(%s,%s,%s,%s,'Statement','Rationale','PLM','HIGH','MEDIUM',"
        "'STANDARD_FUNCTION',%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (version, ids["requirement"], ids["project"], version_no, b"v" * 32,
         sources, acceptance, capability, assumptions, exclusions, dependencies,
         ai_tasks, ids["actor"]),
    )


def insert_human_source(db, ids: dict, version: uuid.UUID, ordinal: int = 0) -> uuid.UUID:
    return db.execute(
        "INSERT INTO plm.req_sources(requirement_version_id,requirement_id,"
        "project_id,ordinal,source_type,source_object_id) VALUES "
        "(%s,%s,%s,%s,'HUMAN_DECISION',%s) RETURNING requirement_source_id",
        (version, ids["requirement"], ids["project"], ordinal, uuid.uuid4()),
    ).fetchone()[0]


def expect_commit_failure(db, expected: str, action) -> None:
    try:
        with db.transaction():
            action()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected deferred closure failure: " + expected)


def main() -> None:
    database = "req01a04a04_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        ids = {
            "actor": uuid.uuid4(), "project": uuid.uuid4(),
            "requirement": uuid.uuid4(),
        }
        unsupported_version = uuid.uuid4()
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.auth_users(user_id,username_display,"
                    "username_normalized,state,deployment_role) VALUES "
                    "(%s,'Requirement support','requirement-support','DISABLED','NONE')",
                    (ids["actor"],),
                )
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES "
                    "(%s,'REQSUP','reqsup','Requirement support project',%s)",
                    (ids["project"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.req_requirements(requirement_id,project_id,"
                    "requirement_code,requirement_code_normalized,created_by) VALUES "
                    "(%s,%s,'REQ-SUPPORT','REQ-SUPPORT',%s)",
                    (ids["requirement"], ids["project"], ids["actor"]),
                )
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                insert_version(db, ids, unsupported_version, 1)
        try:
            command.upgrade(cfg, "head")
        except Exception as error:
            assert "pre-existing RequirementVersion rows require" in str(error), str(error)
        else:
            raise AssertionError("Schema0118 accepted unaudited pre-existing Version")
        with connect(database) as db:
            assert db.execute(
                "SELECT version_num FROM plm.alembic_version"
            ).fetchone()[0] == PREVIOUS
            assert db.execute(
                "SELECT to_regclass('plm.req_version_ai_task_refs')"
            ).fetchone()[0] is None
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "DELETE FROM plm.req_requirement_versions "
                    "WHERE requirement_version_id=%s", (unsupported_version,),
                )
        command.upgrade(cfg, "head")
        command.check(cfg)

        ids.update({
            "global_evidence": uuid.uuid4(),
            "project_evidence": uuid.uuid4(),
            "baseline": uuid.uuid4(),
            "baseline_version": uuid.uuid4(),
            "cap_row": uuid.uuid4(),
            "cap_item": uuid.uuid4(),
            "ai_task": uuid.uuid4(),
            "bad_ai_task": uuid.uuid4(),
        })
        valid_version = uuid.uuid4()
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                for evidence_id, scope, project_id, label in (
                    (ids["global_evidence"], "GLOBAL", None, "Global standard"),
                    (ids["project_evidence"], "PROJECT", ids["project"], "Project fact"),
                ):
                    db.execute(
                        "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,"
                        "document_id,document_version_id,locator_type,locator_schema_version,"
                        "locator_payload,content_fingerprint,display_label,eligibility_state,"
                        "eligibility_reason,created_by) VALUES "
                        "(%s,%s,%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'"
                        "::jsonb,%s,%s,'ELIGIBLE','Support fixture',%s)",
                        (evidence_id, scope, project_id, uuid.uuid4(), uuid.uuid4(),
                         b"e" * 32, label, ids["actor"]),
                    )
                source_ref = "sha256:" + "b" * 64
                db.execute(
                    "INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,"
                    "baseline_state,source_collection_ref,current_approved_version_ref,"
                    "created_by) VALUES (%s,'REQ.SUPPORT','Requirement support capability',"
                    "'ACTIVE',%s,%s,%s)",
                    (ids["baseline"], source_ref, ids["baseline_version"], ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.cap_baseline_versions(baseline_version_id,baseline_id,"
                    "version_no,version_state,source_collection_ref,content_fingerprint,"
                    "declared_item_count,declared_document_ref_count,"
                    "declared_evidence_ref_count,created_by) VALUES "
                    "(%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)",
                    (ids["baseline_version"], ids["baseline"], source_ref,
                     b"c" * 32, ids["actor"]),
                )
                db.execute(
                    "INSERT INTO plm.cap_items(capability_item_row_id,baseline_version_id,"
                    "baseline_id,capability_item_id,ordinal,capability_code,domain_name,"
                    "module_name,feature_name,name,description,boundary_text,item_state) VALUES "
                    "(%s,%s,%s,%s,0,'REQ.SUPPORT.ITEM','PLM','Requirement','Support',"
                    "'Support capability','Support description','Support boundary','AVAILABLE')",
                    (ids["cap_row"], ids["baseline_version"], ids["baseline"],
                     ids["cap_item"]),
                )
                for task_id, suggestion, accepted_module, accepted_version in (
                    (ids["ai_task"], "ACCEPTED_TO_DRAFT", "requirement", valid_version),
                    (ids["bad_ai_task"], "AVAILABLE", None, None),
                ):
                    db.execute(
                        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,"
                        "requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,"
                        "context_policy_ref,task_state,suggestion_state,accepted_domain_module,"
                        "accepted_domain_version_id,trace_id,started_at,completed_at) VALUES "
                        "(%s,'PROJECT',%s,'REQUIREMENT_NORMALIZE',%s,%s,'req-policy-v1',"
                        "'req-schema-v1','req-context-v1','SUCCEEDED',%s,%s,%s,%s,"
                        "statement_timestamp(),statement_timestamp())",
                        (task_id, ids["project"], ids["actor"], b"a" * 32,
                         suggestion, accepted_module, accepted_version, uuid.uuid4()),
                    )

            set_owner_triggers(db, False)
            try:
                with db.transaction():
                    insert_version(
                        db, ids, valid_version, 1, sources=1, acceptance=1,
                        capability=1, assumptions=1, exclusions=1,
                        dependencies=1, ai_tasks=1,
                    )
                    source = db.execute(
                        "INSERT INTO plm.req_sources(requirement_version_id,requirement_id,"
                        "project_id,ordinal,source_type,source_object_id) VALUES "
                        "(%s,%s,%s,0,'PROJECT_EVIDENCE',%s) "
                        "RETURNING requirement_source_id",
                        (valid_version, ids["requirement"], ids["project"],
                         ids["project_evidence"]),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.req_source_evidence_refs(requirement_source_id,"
                        "requirement_version_id,requirement_id,project_id,evidence_id,ordinal) "
                        "VALUES (%s,%s,%s,%s,%s,0)",
                        (source, valid_version, ids["requirement"], ids["project"],
                         ids["project_evidence"]),
                    )
                    db.execute(
                        "INSERT INTO plm.req_acceptance_criteria(requirement_version_id,"
                        "requirement_id,project_id,ordinal,observable_result,"
                        "verification_method,required_data,required_environment,"
                        "evidence_requirement) VALUES (%s,%s,%s,0,'Observable result',"
                        "'Execute acceptance test','Approved data','Windows 11',"
                        "'Signed acceptance evidence')",
                        (valid_version, ids["requirement"], ids["project"]),
                    )
                    assessment = db.execute(
                        "INSERT INTO plm.req_capability_assessments(requirement_version_id,"
                        "requirement_id,project_id,ordinal,baseline_version_id,"
                        "capability_item_id,match_type,fit_gap,constraints_text,assessor_kind,"
                        "assessed_by,assessed_at,confirmation_state) VALUES "
                        "(%s,%s,%s,0,%s,%s,'DIRECT','No gap','Approved constraints',"
                        "'HUMAN',%s,statement_timestamp(),'CONFIRMED') "
                        "RETURNING capability_assessment_id",
                        (valid_version, ids["requirement"], ids["project"],
                         ids["baseline_version"], ids["cap_item"], ids["actor"]),
                    ).fetchone()[0]
                    for ordinal, evidence_id, role in (
                        (0, ids["global_evidence"], "STANDARD"),
                        (1, ids["project_evidence"], "PROJECT"),
                    ):
                        db.execute(
                            "INSERT INTO plm.req_assessment_evidence_refs("
                            "capability_assessment_id,requirement_version_id,requirement_id,"
                            "project_id,evidence_id,evidence_role,ordinal) VALUES "
                            "(%s,%s,%s,%s,%s,%s,%s)",
                            (assessment, valid_version, ids["requirement"], ids["project"],
                             evidence_id, role, ordinal),
                        )
                    db.execute(
                        "INSERT INTO plm.req_assumptions(requirement_version_id,requirement_id,"
                        "project_id,ordinal,assumption_text) VALUES "
                        "(%s,%s,%s,0,'Approved master data is available')",
                        (valid_version, ids["requirement"], ids["project"]),
                    )
                    db.execute(
                        "INSERT INTO plm.req_exclusions(requirement_version_id,requirement_id,"
                        "project_id,ordinal,exclusion_text) VALUES "
                        "(%s,%s,%s,0,'Legacy cleansing is excluded')",
                        (valid_version, ids["requirement"], ids["project"]),
                    )
                    db.execute(
                        "INSERT INTO plm.req_dependencies(requirement_version_id,"
                        "requirement_id,project_id,ordinal,dependency_text) VALUES "
                        "(%s,%s,%s,0,'ERP interface availability')",
                        (valid_version, ids["requirement"], ids["project"]),
                    )
                    db.execute(
                        "INSERT INTO plm.req_version_ai_task_refs(requirement_version_id,"
                        "requirement_id,project_id,ai_task_id,ordinal) VALUES "
                        "(%s,%s,%s,%s,0)",
                        (valid_version, ids["requirement"], ids["project"], ids["ai_task"]),
                    )

                def bad_count():
                    insert_version(db, ids, uuid.uuid4(), 2, sources=2)
                expect_commit_failure(db, "declared counts do not match", bad_count)

                def bad_order():
                    version = uuid.uuid4()
                    insert_version(db, ids, version, 2)
                    insert_human_source(db, ids, version, ordinal=1)
                expect_commit_failure(db, "ordinals are not contiguous", bad_order)

                def missing_assessment_proof():
                    version = uuid.uuid4()
                    insert_version(db, ids, version, 2, capability=1)
                    insert_human_source(db, ids, version)
                    db.execute(
                        "INSERT INTO plm.req_capability_assessments(requirement_version_id,"
                        "requirement_id,project_id,ordinal,baseline_version_id,"
                        "capability_item_id,match_type,fit_gap,constraints_text,assessor_kind,"
                        "assessed_by,assessed_at,confirmation_state) VALUES "
                        "(%s,%s,%s,0,%s,%s,'DIRECT','No gap','Constraints','HUMAN',%s,"
                        "statement_timestamp(),'CONFIRMED')",
                        (version, ids["requirement"], ids["project"],
                         ids["baseline_version"], ids["cap_item"], ids["actor"]),
                    )
                expect_commit_failure(
                    db, "requires STANDARD and PROJECT Evidence", missing_assessment_proof,
                )

                def missing_project_source_proof():
                    version = uuid.uuid4()
                    insert_version(db, ids, version, 2)
                    db.execute(
                        "INSERT INTO plm.req_sources(requirement_version_id,requirement_id,"
                        "project_id,ordinal,source_type,source_object_id) VALUES "
                        "(%s,%s,%s,0,'PROJECT_EVIDENCE',%s)",
                        (version, ids["requirement"], ids["project"],
                         ids["project_evidence"]),
                    )
                expect_commit_failure(
                    db, "requires matching Evidence reference", missing_project_source_proof,
                )

                def wrong_assessment_scope():
                    version = uuid.uuid4()
                    insert_version(db, ids, version, 2, capability=1)
                    insert_human_source(db, ids, version)
                    assessment = db.execute(
                        "INSERT INTO plm.req_capability_assessments(requirement_version_id,"
                        "requirement_id,project_id,ordinal,baseline_version_id,"
                        "capability_item_id,match_type,fit_gap,constraints_text,assessor_kind,"
                        "assessed_by,assessed_at,confirmation_state) VALUES "
                        "(%s,%s,%s,0,%s,%s,'DIRECT','No gap','Constraints','HUMAN',%s,"
                        "statement_timestamp(),'CONFIRMED') RETURNING capability_assessment_id",
                        (version, ids["requirement"], ids["project"],
                         ids["baseline_version"], ids["cap_item"], ids["actor"]),
                    ).fetchone()[0]
                    for ordinal, evidence_id, role in (
                        (0, ids["project_evidence"], "STANDARD"),
                        (1, ids["global_evidence"], "PROJECT"),
                    ):
                        db.execute(
                            "INSERT INTO plm.req_assessment_evidence_refs("
                            "capability_assessment_id,requirement_version_id,requirement_id,"
                            "project_id,evidence_id,evidence_role,ordinal) VALUES "
                            "(%s,%s,%s,%s,%s,%s,%s)",
                            (assessment, version, ids["requirement"], ids["project"],
                             evidence_id, role, ordinal),
                        )
                expect_commit_failure(
                    db, "Evidence scope or eligibility is invalid", wrong_assessment_scope,
                )

                def bad_ai():
                    version = uuid.uuid4()
                    insert_version(db, ids, version, 2, ai_tasks=1)
                    insert_human_source(db, ids, version)
                    db.execute(
                        "INSERT INTO plm.req_version_ai_task_refs(requirement_version_id,"
                        "requirement_id,project_id,ai_task_id,ordinal) VALUES "
                        "(%s,%s,%s,%s,0)",
                        (version, ids["requirement"], ids["project"], ids["bad_ai_task"]),
                    )
                expect_commit_failure(db, "not accepted to this draft", bad_ai)
            finally:
                set_owner_triggers(db, True)

            assert db.execute(
                "SELECT count(*) FROM plm.req_requirement_versions"
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.req_assessment_evidence_refs"
            ).fetchone()[0] == 2
            try:
                with db.transaction():
                    db.execute(
                        "DELETE FROM plm.req_version_ai_task_refs WHERE ai_task_id=%s",
                        (ids["ai_task"],),
                    )
            except psycopg.Error as error:
                assert "RequirementVersion support Owner is not installed" in str(error)
            else:
                raise AssertionError("support Owner accepted direct delete")
            try:
                with db.transaction():
                    db.execute("TRUNCATE plm.req_version_ai_task_refs")
            except psycopg.Error as error:
                assert "support history cannot be truncated" in str(error)
            else:
                raise AssertionError("support history accepted truncate")

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "RequirementVersion support history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0118 accepted support history")
        print(
            "REQ_01_A04_A04_VERSION_SUPPORT_PASS: audited existing-data upgrade, "
            "normalized Evidence/AI refs, exact declared counts, contiguous ordinals, "
            "dual assessment proof, PROJECT Evidence identity, accepted-to-draft AI, "
            "closed Owner, truncate and history downgrade refusal verified on PostgreSQL 18"
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
