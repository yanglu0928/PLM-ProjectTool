"""Requirement browser fixture: isolated PostgreSQL 18 plus production Windows composition."""
from __future__ import annotations
import importlib.util
import uuid
from pathlib import Path
from unittest.mock import patch
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec

ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/"validation/sur-05-a05-conclusion-browser/serve.py"
spec=importlib.util.spec_from_file_location("req_browser_base",PATH);assert spec is not None and spec.loader is not None
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
schema=base.schema; original_seed=schema.seed_dependencies

def seed_with_requirement(db):
    ids=original_seed(db); requirement=uuid.uuid4()
    standard_file,standard_document,standard_version,standard_evidence=(uuid.uuid4() for _ in range(4))
    cap_review,cap_round,cap_snapshot=(uuid.uuid4() for _ in range(3))
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("""INSERT INTO plm.req_requirements(
          requirement_id,project_id,requirement_code,requirement_code_normalized,created_by)
          VALUES (%s,%s,'REQ-EDGE-001','REQ-EDGE-001',%s)""",(requirement,ids["project"],ids["actor"]))
        db.execute("""INSERT INTO plm.doc_file_objects(file_object_id,scope,storage_class,storage_locator,
          original_name_metadata,sha256,size_bytes,detected_mime,file_state,created_by,available_at)
          VALUES (%s,'GLOBAL','PERSISTENT','standard/source.pdf','standard.pdf',%s,16,
          'application/pdf','AVAILABLE',%s,statement_timestamp())""",(standard_file,b"g"*32,ids["actor"]))
        db.execute("""INSERT INTO plm.doc_documents(document_id,scope,document_category,title,
          original_display_name,document_state,created_by) VALUES (%s,'GLOBAL','TEMPLATE',
          'Standard capability source','standard.pdf','ACTIVE',%s)""",(standard_document,ids["actor"]))
        db.execute("""INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,
          version_no,file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by,
          availability_state,integrity_checked_at) VALUES (%s,%s,'GLOBAL',1,%s,%s,16,
          'application/pdf','{}'::jsonb,%s,'AVAILABLE',statement_timestamp())""",
          (standard_version,standard_document,standard_file,b"g"*32,ids["actor"]))
        db.execute("""INSERT INTO plm.evd_evidence_records(evidence_id,scope,document_id,
          document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,
          display_label,display_excerpt,eligibility_state,eligibility_reason,created_by)
          VALUES (%s,'GLOBAL',%s,%s,'DOCUMENT',1,'{"locator_type":"DOCUMENT"}'::jsonb,%s,
          'Standard capability evidence','Synthetic standard evidence','ELIGIBLE','browser fixture',%s)""",
          (standard_evidence,standard_document,standard_version,b"g"*32,ids["actor"]))
        db.execute("""INSERT INTO plm.cap_item_evidence_refs(capability_item_row_id,
          baseline_version_id,baseline_id,evidence_id,ordinal) VALUES (%s,%s,%s,%s,0)""",
          (ids["capability_item_row"],ids["baseline_version"],ids["baseline"],standard_evidence))
        db.execute("""INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,
          subject_id,policy_code,review_state,active_round_id,lock_version,created_by)
          VALUES (%s,'GLOBAL',NULL,'CAP-01',%s,'DEPLOYMENT_ALL_V1','APPROVED',NULL,2,%s)""",
          (cap_review,ids["baseline"],ids["actor"]))
        db.execute("""INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,
          project_id,round_no,subject_version_id,round_state,lock_version,started_by,started_at)
          VALUES (%s,%s,'GLOBAL',NULL,1,%s,'APPROVED',1,%s,statement_timestamp())""",
          (cap_round,cap_review,ids["baseline_version"],ids["actor"]))
        db.execute("""INSERT INTO plm.rvw_subject_snapshots(snapshot_id,review_id,
          review_round_id,scope,project_id,subject_type,subject_id,subject_version_id,
          content_fingerprint,proof_schema_version,verified_at)
          VALUES (%s,%s,%s,'GLOBAL',NULL,'CAP-01',%s,%s,%s,1,statement_timestamp())""",
          (cap_snapshot,cap_review,cap_round,ids["baseline"],ids["baseline_version"],b"c"*32))
        db.execute("""UPDATE plm.cap_baseline_versions SET review_ref=%s,review_round_ref=%s
          WHERE baseline_version_id=%s""",(cap_review,cap_round,ids["baseline_version"]))
    ids["requirement"]=requirement
    return ids

schema.seed_dependencies=seed_with_requirement

if __name__=="__main__":
    with patch("plm_assistant.entrypoints.production_login.create_windows_evidence_list_cursor_codec",return_value=EvidenceListCursorCodec(b"e"*32)), patch("plm_assistant.entrypoints.windows_requirement.WindowsSecretKeyProvider",return_value=base.base.base.base.Keys()):
        base.base.base.base.main()
