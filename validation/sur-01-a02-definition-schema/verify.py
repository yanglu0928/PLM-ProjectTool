"""Windows 11/PostgreSQL 18 proof for Schema0103 Survey definition foundation."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261005_0102"


def connect(database: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=database,
                           autocommit=True, connect_timeout=5)


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=database,
    ))


def reject(operation, expected: str) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def seed_dependencies(db):
    ids = {name: uuid.uuid4() for name in (
        "actor", "project", "department", "template_file", "template_document",
        "template_version", "record_file", "record_document", "record_version",
        "baseline", "baseline_version", "capability_item_row", "capability_item",
        "analysis", "analysis_version", "handover_item_row", "handover_item",
    )}
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("""
            INSERT INTO plm.auth_users(user_id,username_display,username_normalized,
              state,deployment_role)
            VALUES (%s,'Survey schema actor','survey-schema-actor','DISABLED','NONE')
        """, (ids["actor"],))
        db.execute("""
            INSERT INTO plm.prj_projects(project_id,project_code,
              project_code_normalized,name,created_by)
            VALUES (%s,'SUR001','sur001','Survey schema',%s)
        """, (ids["project"], ids["actor"]))
        db.execute("""
            INSERT INTO plm.prj_departments(department_id,project_id,department_code,
              department_code_normalized,name)
            VALUES (%s,%s,'BUSINESS','business','Business')
        """, (ids["department"], ids["project"]))
        _document(db, ids, "template", "GLOBAL", None, "TEMPLATE")
        _document(db, ids, "record", "PROJECT", ids["project"], "PROJECT_RECORD")
        source_ref = "sha256:" + "a" * 64
        db.execute("""
            INSERT INTO plm.cap_baselines(
              baseline_id,baseline_code,name,baseline_state,source_collection_ref,
              current_approved_version_ref,created_by)
            VALUES (%s,'SUR.CAP','Survey capability','ACTIVE',%s,%s,%s)
        """, (ids["baseline"], source_ref, ids["baseline_version"], ids["actor"]))
        db.execute("""
            INSERT INTO plm.cap_baseline_versions(
              baseline_version_id,baseline_id,version_no,version_state,
              source_collection_ref,content_fingerprint,declared_item_count,
              declared_document_ref_count,declared_evidence_ref_count,created_by)
            VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)
        """, (ids["baseline_version"], ids["baseline"], source_ref,
                b"c" * 32, ids["actor"]))
        db.execute("""
            INSERT INTO plm.cap_items(
              capability_item_row_id,baseline_version_id,baseline_id,
              capability_item_id,ordinal,capability_code,domain_name,module_name,
              feature_name,name,description,boundary_text,item_state)
            VALUES (%s,%s,%s,%s,0,'SUR.CAP.ITEM','PLM','Survey','Interview',
              'Interview','Interview support','Reference only','AVAILABLE')
        """, (ids["capability_item_row"], ids["baseline_version"],
                ids["baseline"], ids["capability_item"]))
        db.execute("""
            INSERT INTO plm.hnd_analyses(
              handover_analysis_id,project_id,analysis_purpose,source_set_ref,
              analysis_state,current_approved_version_ref,created_by)
            VALUES (%s,%s,'Survey input',%s,'ACTIVE',%s,%s)
        """, (ids["analysis"], ids["project"], source_ref,
                ids["analysis_version"], ids["actor"]))
        db.execute("""
            INSERT INTO plm.hnd_analysis_versions(
              handover_analysis_version_id,handover_analysis_id,project_id,
              version_no,version_state,source_set_ref,capability_baseline_id,
              capability_baseline_version_ref,content_fingerprint,
              declared_source_count,declared_item_count,declared_evidence_count,
              declared_capability_ref_count,declared_ai_task_count,created_by)
            VALUES (%s,%s,%s,1,'APPROVED',%s,%s,%s,%s,1,1,1,1,0,%s)
        """, (ids["analysis_version"], ids["analysis"], ids["project"],
                source_ref, ids["baseline"], ids["baseline_version"], b"h" * 32,
                ids["actor"]))
        db.execute("""
            INSERT INTO plm.hnd_analysis_items(
              analysis_item_row_id,handover_analysis_version_id,
              handover_analysis_id,project_id,analysis_item_id,ordinal,item_type,
              title,statement,impact,severity,priority,required_input_spec,
              source_missing,item_state)
            VALUES (%s,%s,%s,%s,%s,0,'SCOPE','Survey scope',
              'Survey the business process','Defines requirements','MEDIUM','HIGH',
              '{}'::jsonb,false,'CONFIRMED')
        """, (ids["handover_item_row"], ids["analysis_version"], ids["analysis"],
                ids["project"], ids["handover_item"]))
    return ids


def _document(db, ids, prefix: str, scope: str, project_id, category: str) -> None:
    db.execute("""
        INSERT INTO plm.doc_file_objects(
          file_object_id,scope,project_id,storage_class,storage_locator,
          original_name_metadata,sha256,size_bytes,detected_mime,file_state,
          created_by,available_at)
        VALUES (%s,%s,%s,'PERSISTENT',%s,%s,%s,16,'application/pdf','AVAILABLE',
          %s,statement_timestamp())
    """, (ids[prefix + "_file"], scope, project_id, prefix + "/source.pdf",
            prefix + ".pdf", prefix.encode().ljust(32, b"x")[:32], ids["actor"]))
    db.execute("""
        INSERT INTO plm.doc_documents(
          document_id,scope,project_id,document_category,title,
          original_display_name,document_state,created_by)
        VALUES (%s,%s,%s,%s,%s,%s,'ACTIVE',%s)
    """, (ids[prefix + "_document"], scope, project_id, category,
            prefix.title(), prefix + ".pdf", ids["actor"]))
    db.execute("""
        INSERT INTO plm.doc_document_versions(
          document_version_id,document_id,scope,project_id,version_no,
          file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,
          created_by,availability_state,integrity_checked_at)
        VALUES (%s,%s,%s,%s,1,%s,%s,16,'application/pdf','{}'::jsonb,%s,
          'AVAILABLE',statement_timestamp())
    """, (ids[prefix + "_version"], ids[prefix + "_document"], scope,
            project_id, ids[prefix + "_file"],
            (prefix + "-content").encode().ljust(32, b"x")[:32], ids["actor"]))


def insert_valid(db, ids, *, name: str = "Business survey"):
    survey, version = uuid.uuid4(), uuid.uuid4()
    questions = [uuid.uuid4() for _ in range(4)]
    stable = [uuid.uuid4() for _ in range(4)]
    with db.transaction():
        db.execute("""
            INSERT INTO plm.srv_surveys(survey_id,project_id,name,created_by)
            VALUES (%s,%s,%s,%s)
        """, (survey, ids["project"], name, ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_survey_versions(
              survey_version_id,survey_id,project_id,version_no,
              content_fingerprint,declared_question_count,declared_option_count,
              declared_source_count,declared_target_department_count,created_by)
            VALUES (%s,%s,%s,1,%s,4,2,4,1,%s)
        """, (version, survey, ids["project"], b"s" * 32, ids["actor"]))
        answer_types = ("TEXT", "TEXT", "SINGLE_CHOICE", "TEXT")
        for sequence, (row_id, question_id, answer_type) in enumerate(
                zip(questions, stable, answer_types, strict=True)):
            db.execute("""
                INSERT INTO plm.srv_questions(
                  question_row_id,survey_version_id,survey_id,project_id,
                  question_id,sequence_no,topic,question_text,objective,
                  answer_type,validation_rule,required,expected_output,
                  evidence_required)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,true,%s,false)
            """, (row_id, version, survey, ids["project"], question_id, sequence,
                    "Topic " + str(sequence), "Question " + str(sequence),
                    "Objective " + str(sequence), answer_type,
                    "Expected " + str(sequence)))
        for ordinal, code in enumerate(("YES", "NO")):
            db.execute("""
                INSERT INTO plm.srv_question_options(
                  question_row_id,survey_version_id,survey_id,project_id,
                  option_code,label,ordinal)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (questions[2], version, survey, ids["project"], code,
                    code.title(), ordinal))
        common = (version, survey, ids["project"])
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              handover_item_row_id,handover_analysis_version_id,
              handover_analysis_id,ordinal)
            VALUES (%s,%s,%s,%s,'HANDOVER_ITEM',%s,%s,%s,0)
        """, (questions[0], *common, ids["handover_item_row"],
                ids["analysis_version"], ids["analysis"]))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              capability_item_row_id,capability_baseline_version_id,
              capability_baseline_id,ordinal)
            VALUES (%s,%s,%s,%s,'CAPABILITY_ITEM',%s,%s,%s,0)
        """, (questions[1], *common, ids["capability_item_row"],
                ids["baseline_version"], ids["baseline"]))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              template_document_version_id,template_document_id,ordinal)
            VALUES (%s,%s,%s,%s,'TEMPLATE_DOCUMENT_VERSION',%s,%s,0)
        """, (questions[2], *common, ids["template_version"],
                ids["template_document"]))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              manual_source_note,ordinal)
            VALUES (%s,%s,%s,%s,'MANUAL','Project manager confirmed question',0)
        """, (questions[3], *common))
        db.execute("""
            INSERT INTO plm.srv_target_departments(
              survey_version_id,survey_id,project_id,department_id,ordinal)
            VALUES (%s,%s,%s,%s,0)
        """, (version, survey, ids["project"], ids["department"]))
    return survey, version


def insert_bad_template(db, ids):
    survey, version, question = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("INSERT INTO plm.srv_surveys(survey_id,project_id,name,created_by) "
                   "VALUES (%s,%s,'Bad template survey',%s)",
                   (survey, ids["project"], ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_survey_versions(
              survey_version_id,survey_id,project_id,version_no,
              content_fingerprint,declared_question_count,declared_option_count,
              declared_source_count,declared_target_department_count,created_by)
            VALUES (%s,%s,%s,1,%s,1,0,1,1,%s)
        """, (version, survey, ids["project"], b"b" * 32, ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_questions(
              question_row_id,survey_version_id,survey_id,project_id,question_id,
              sequence_no,topic,question_text,objective,answer_type,
              expected_output)
            VALUES (%s,%s,%s,%s,%s,0,'Bad','Bad source?','Reject record as template',
              'TEXT','Rejected')
        """, (question, version, survey, ids["project"], uuid.uuid4()))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              template_document_version_id,template_document_id,ordinal)
            VALUES (%s,%s,%s,%s,'TEMPLATE_DOCUMENT_VERSION',%s,%s,0)
        """, (question, version, survey, ids["project"], ids["record_version"],
                ids["record_document"]))
        db.execute("INSERT INTO plm.srv_target_departments(survey_version_id,"
                   "survey_id,project_id,department_id,ordinal) VALUES (%s,%s,%s,%s,0)",
                   (version, survey, ids["project"], ids["department"]))


def insert_choice_without_options(db, ids):
    survey, version, question = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("INSERT INTO plm.srv_surveys(survey_id,project_id,name,created_by) "
                   "VALUES (%s,%s,'Incomplete choice survey',%s)",
                   (survey, ids["project"], ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_survey_versions(
              survey_version_id,survey_id,project_id,version_no,
              content_fingerprint,declared_question_count,declared_option_count,
              declared_source_count,declared_target_department_count,created_by)
            VALUES (%s,%s,%s,1,%s,1,0,1,1,%s)
        """, (version, survey, ids["project"], b"o" * 32, ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_questions(
              question_row_id,survey_version_id,survey_id,project_id,question_id,
              sequence_no,topic,question_text,objective,answer_type,
              expected_output)
            VALUES (%s,%s,%s,%s,%s,0,'Choice','Choose one','Require options',
              'SINGLE_CHOICE','One selected option')
        """, (question, version, survey, ids["project"], uuid.uuid4()))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              manual_source_note,ordinal)
            VALUES (%s,%s,%s,%s,'MANUAL','Product owner supplied structure',0)
        """, (question, version, survey, ids["project"]))
        db.execute("INSERT INTO plm.srv_target_departments(survey_version_id,"
                   "survey_id,project_id,department_id,ordinal) VALUES (%s,%s,%s,%s,0)",
                   (version, survey, ids["project"], ids["department"]))


def main() -> None:
    database = "sur01a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        cfg = config(database)
        command.upgrade(cfg, PREVIOUS)
        existing = uuid.uuid4()
        with connect(database) as db:
            db.execute("INSERT INTO plm.auth_users(user_id,username_display,"
                       "username_normalized,state,deployment_role) VALUES "
                       "(%s,'Existing','existing-survey','DISABLED','NONE')", (existing,))
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s",
                              (existing,)).fetchone()[0] == 1
            tables = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='plm' AND table_name LIKE 'srv_%'"
            )}
            assert tables == set(("srv_surveys", "srv_survey_versions", "srv_questions",
                                  "srv_question_options", "srv_question_source_refs",
                                  "srv_target_departments")), tables
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = seed_dependencies(db)
            survey, version = insert_valid(db, ids)
            counts = db.execute("""
                SELECT (SELECT count(*) FROM plm.srv_questions WHERE survey_version_id=%s),
                       (SELECT count(*) FROM plm.srv_question_options WHERE survey_version_id=%s),
                       (SELECT count(*) FROM plm.srv_question_source_refs WHERE survey_version_id=%s),
                       (SELECT count(*) FROM plm.srv_target_departments WHERE survey_version_id=%s)
            """, (version, version, version, version)).fetchone()
            assert counts == (4, 2, 4, 1), counts
            reject(lambda: insert_bad_template(db, ids),
                   "Survey template source is invalid")
            reject(lambda: insert_choice_without_options(db, ids),
                   "Survey choice options are incomplete")
            reject(lambda: db.execute("UPDATE plm.srv_surveys SET name='Changed' "
                                      "WHERE survey_id=%s", (survey,)),
                   "Survey Owner transition is invalid")
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert ("Survey definition history prevents downgrade" in str(error)
                    or "Survey Version history prevents downgrade" in str(error)), str(error)
        else:
            raise AssertionError("Schema0103 accepted retained Survey history")
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "SUR_01_A02_DEFINITION_SCHEMA_PASS: Schema0103 existing/empty upgrade, "
        "empty downgrade/re-upgrade, drift, typed Handover/Capability/TEMPLATE/manual "
        "sources, target department, template boundary, owner closure and retained-history "
        "refusal plus choice completeness verified on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
