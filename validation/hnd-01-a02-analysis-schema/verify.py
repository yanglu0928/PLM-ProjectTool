"""Windows 11/PostgreSQL 18 proof for Schema0096 Handover analysis foundation."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261005_0095"


def connect(database):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=database,
                           autocommit=True, connect_timeout=5)


def config(database):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=database,
    ))


def source_ref(version_id):
    return "sha256:" + hashlib.sha256(
        f"handover-source-set.v1\n{version_id}".encode()
    ).hexdigest()


def reject(operation, expected):
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def seed_dependencies(db):
    actor, project = uuid.uuid4(), uuid.uuid4()
    file_id, document, document_version, evidence = (uuid.uuid4() for _ in range(4))
    baseline, baseline_version, item_row, item = (uuid.uuid4() for _ in range(4))
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized,state,deployment_role) VALUES (%s,'Handover actor','handover-actor','DISABLED','NONE')", (actor,))
        db.execute("INSERT INTO plm.prj_projects(project_id,project_code,project_code_normalized,name,created_by) VALUES (%s,'HND001','hnd001','Handover schema',%s)", (project, actor))
        db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,file_state,created_by,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT','handover/source.pdf','source.pdf',%s,16,'application/pdf','AVAILABLE',%s,statement_timestamp())", (file_id, project, b'f'*32, actor))
        db.execute("INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,title,original_display_name,document_state,created_by) VALUES (%s,'PROJECT',%s,'PROJECT_RECORD','Handover source','source.pdf','ACTIVE',%s)", (document, project, actor))
        db.execute("INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,project_id,version_no,file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by,availability_state,integrity_checked_at) VALUES (%s,%s,'PROJECT',%s,1,%s,%s,16,'application/pdf','{}'::jsonb,%s,'AVAILABLE',statement_timestamp())", (document_version, document, project, file_id, b'd'*32, actor))
        db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Handover evidence','ELIGIBLE','fixture',%s)", (evidence, project, document, document_version, b'e'*32, actor))
        cap_ref = "sha256:" + "a"*64
        db.execute("INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,baseline_state,source_collection_ref,current_approved_version_ref,created_by) VALUES (%s,'HND.CAP','Handover capability','ACTIVE',%s,%s,%s)", (baseline, cap_ref, baseline_version, actor))
        db.execute("INSERT INTO plm.cap_baseline_versions(baseline_version_id,baseline_id,version_no,version_state,source_collection_ref,content_fingerprint,declared_item_count,declared_document_ref_count,declared_evidence_ref_count,created_by) VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)", (baseline_version, baseline, cap_ref, b'c'*32, actor))
        db.execute("INSERT INTO plm.cap_items(capability_item_row_id,baseline_version_id,baseline_id,capability_item_id,ordinal,capability_code,domain_name,module_name,feature_name,name,description,boundary_text,item_state) VALUES (%s,%s,%s,%s,0,'HND.CAP.ITEM','PLM','Handover','Analysis','Handover','Handover analysis','Project only','AVAILABLE')", (item_row, baseline_version, baseline, item))
    return actor, project, document, document_version, evidence, baseline, baseline_version, item


def insert_valid(db, deps, *, ref=None, need_options=True):
    actor, project, document, document_version, evidence, baseline, baseline_version, item = deps
    analysis, version, item_row, stable_item = (uuid.uuid4() for _ in range(4))
    fingerprint = ref or source_ref(document_version)
    with db.transaction():
        db.execute("INSERT INTO plm.hnd_analyses(handover_analysis_id,project_id,analysis_purpose,source_set_ref,created_by) VALUES (%s,%s,'Project handover',%s,%s)", (analysis, project, fingerprint, actor))
        db.execute("INSERT INTO plm.hnd_analysis_versions(handover_analysis_version_id,handover_analysis_id,project_id,version_no,source_set_ref,capability_baseline_id,capability_baseline_version_ref,content_fingerprint,declared_source_count,declared_item_count,declared_evidence_count,declared_capability_ref_count,declared_ai_task_count,created_by) VALUES (%s,%s,%s,1,%s,%s,%s,%s,1,1,1,1,0,%s)", (version, analysis, project, fingerprint, baseline, baseline_version, b'v'*32, actor))
        db.execute("INSERT INTO plm.hnd_analysis_source_document_refs(handover_analysis_version_id,handover_analysis_id,project_id,document_id,document_version_id,ordinal) VALUES (%s,%s,%s,%s,%s,0)", (version, analysis, project, document, document_version))
        db.execute("INSERT INTO plm.hnd_analysis_items(analysis_item_row_id,handover_analysis_version_id,handover_analysis_id,project_id,analysis_item_id,ordinal,item_type,title,statement,impact,severity,priority,recommendation,confirmation_question,required_input_spec,item_state) VALUES (%s,%s,%s,%s,%s,0,'NEED_CONFIRM','Confirm scope','Customer scope requires confirmation','Scope affects delivery','HIGH','HIGH','Confirm option A','Which scope is approved?','{\"fields\":[{\"name\":\"scope\",\"format\":\"text\",\"example\":\"A\",\"required\":true}]}'::jsonb,'CANDIDATE')", (item_row, version, analysis, project, stable_item))
        db.execute("INSERT INTO plm.hnd_item_evidence_refs(analysis_item_row_id,handover_analysis_version_id,handover_analysis_id,project_id,evidence_id,ordinal) VALUES (%s,%s,%s,%s,%s,0)", (item_row, version, analysis, project, evidence))
        db.execute("INSERT INTO plm.hnd_item_capability_refs(analysis_item_row_id,handover_analysis_version_id,handover_analysis_id,project_id,baseline_version_id,capability_item_id,ordinal) VALUES (%s,%s,%s,%s,%s,%s,0)", (item_row, version, analysis, project, baseline_version, item))
        if need_options:
            for ordinal, code in enumerate(('A','B')):
                db.execute("INSERT INTO plm.hnd_item_options(analysis_item_row_id,handover_analysis_version_id,handover_analysis_id,project_id,option_code,label,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s)", (item_row, version, analysis, project, code, 'Option '+code, ordinal))
    return analysis, version


def main():
    name = "hnd01a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        cfg = config(name)
        command.upgrade(cfg, PREVIOUS)
        with connect(name) as db:
            actor = uuid.uuid4()
            db.execute("INSERT INTO plm.auth_users(user_id,username_display,username_normalized,state,deployment_role) VALUES (%s,'Existing','existing-hnd','DISABLED','NONE')", (actor,))
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (actor,)).fetchone()[0] == 1
            tables = {row[0] for row in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='plm' AND table_name LIKE 'hnd_%'")}
            assert tables == set(("hnd_analyses", "hnd_analysis_versions", "hnd_analysis_source_document_refs", "hnd_analysis_ai_task_refs", "hnd_analysis_items", "hnd_item_evidence_refs", "hnd_item_capability_refs", "hnd_item_options")), tables
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        with connect(name) as db:
            deps = seed_dependencies(db)
            analysis, version = insert_valid(db, deps)
            assert db.execute("SELECT count(*) FROM plm.hnd_analysis_items WHERE handover_analysis_version_id=%s", (version,)).fetchone()[0] == 1
            reject(lambda: insert_valid(db, deps, ref="sha256:"+"0"*64), "source set fingerprint is invalid")
            reject(lambda: insert_valid(db, deps, need_options=False), "NEED_CONFIRM prompt is incomplete")
            reject(lambda: db.execute("UPDATE plm.hnd_analyses SET analysis_purpose='changed' WHERE handover_analysis_id=%s", (analysis,)), "Handover Analysis Owner")
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert any(message in str(error) for message in (
                "Handover Version history prevents downgrade",
                "Handover analysis history prevents downgrade",
            )), str(error)
        else:
            raise AssertionError("Schema0096 accepted retained Handover history")
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    print("HND_01_A02_ANALYSIS_SCHEMA_PASS: Schema0096 upgrade/downgrade/re-upgrade, drift, fixed project sources, approved capability input, NEED_CONFIRM shape, owner closure and retained-history refusal verified on PostgreSQL 18")


if __name__ == "__main__":
    main()
