"""Windows 11/PostgreSQL 18 proof for auditable Handover validation reports."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.task_read_repository import SqlAlchemyAITaskReadRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.handover_validation_source import SqlAlchemyHandoverValidationAuditSource
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.capability.infrastructure.read_repository import SqlAlchemyCapabilityReadRepository
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.handover.application.create_analysis import CreateHandoverAnalysis, HandoverAnalysisCreateService
from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, HandoverAnalysisItemDraft, HandoverCapabilityItemRef,
    HandoverItemOptionDraft, HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.source_validation import HandoverSourceValidator
from plm_assistant.modules.handover.application.validate_version import ValidateHandoverVersion, HandoverVersionValidationService
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import SqlAlchemyHandoverAnalysisCreateRepository
from plm_assistant.modules.handover.infrastructure.version_create_repository import SqlAlchemyHandoverVersionCreateRepository
from plm_assistant.modules.handover.infrastructure.version_validation_repository import SqlAlchemyHandoverVersionValidationRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


ROOT = Path(__file__).resolve().parents[2]
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_p03_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def main():
    name = "hnd01a03p03_" + uuid.uuid4().hex[:8]
    token = b"w" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Handover Validation PM", "NONE", token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDVAL','hndval','Handover Validate',%s) RETURNING project_id", (actor,)).fetchone()[0]
                    dept = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, dept))
                    source = p01.seed_project_document(db, actor, project, "validate-source")
                    evidence, baseline, cap_version, cap_item, ai_task, cap_row = (uuid.uuid4() for _ in range(6))
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Validation evidence','ELIGIBLE','fixture',%s)", (evidence, project, source.document_id, source.document_version_id, b'e'*32, actor))
                        cap_ref="sha256:"+"b"*64
                        db.execute("INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,baseline_state,source_collection_ref,current_approved_version_ref,created_by) VALUES (%s,'HND.VALIDATE','Validate','ACTIVE',%s,%s,%s)", (baseline,cap_ref,cap_version,actor))
                        db.execute("INSERT INTO plm.cap_baseline_versions(baseline_version_id,baseline_id,version_no,version_state,source_collection_ref,content_fingerprint,declared_item_count,declared_document_ref_count,declared_evidence_ref_count,created_by) VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)", (cap_version,baseline,cap_ref,b'c'*32,actor))
                        db.execute("INSERT INTO plm.cap_items(capability_item_row_id,baseline_version_id,baseline_id,capability_item_id,ordinal,capability_code,domain_name,module_name,feature_name,name,description,boundary_text,item_state) VALUES (%s,%s,%s,%s,0,'HND.VALIDATE.ITEM','PLM','Handover','Validate','Validate','Validate capability','Project only','AVAILABLE')", (cap_row,cap_version,baseline,cap_item))
                        db.execute("INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,task_state,suggestion_state,trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap.v1','gap.output.v1','project.v1','SUCCEEDED','AVAILABLE',%s,statement_timestamp(),statement_timestamp())", (ai_task,project,actor,b'a'*32,uuid.uuid4()))
                        db.execute("INSERT INTO plm.ai_task_input_refs(input_ref_id,ai_task_id,ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id) VALUES (%s,%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)", (uuid.uuid4(),ai_task,project,source.document_id,source.document_version_id))

                guard=Guard(); auth=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository())
                access=SqlAlchemyProjectWriteAccess(); sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository())
                evidence_port=SqlAlchemyEvidenceFixedSourceRepository(); cap_port=SqlAlchemyCapabilityReadRepository(); ai_port=SqlAlchemyAITaskReadRepository()
                receipts=SqlAlchemyIdempotencyReceipts(); audit=AuditService(SqlAlchemyAuditRepository())
                analysis=HandoverAnalysisCreateService(unit_of_work=runtime.unit_of_work,access=access,license_guard=guard,authorization=auth,sources=sources,repository=SqlAlchemyHandoverAnalysisCreateRepository(),receipts=receipts,audit=audit).create(CreateHandoverAnalysis(token,CSRF,uuid.uuid4(),project,"Validation handover",(source,),str(uuid.uuid4())))
                creator=HandoverVersionCreateService(unit_of_work=runtime.unit_of_work,access=access,license_guard=guard,authorization=auth,sources=sources,evidence=evidence_port,capabilities=cap_port,ai_tasks=ai_port,repository=SqlAlchemyHandoverVersionCreateRepository(),receipts=receipts,audit=audit)
                def draft(source_missing=False):
                    return HandoverAnalysisItemDraft(uuid.uuid4(),"NEED_CONFIRM" if not source_missing else "MISSING","Confirm scope" if not source_missing else "Missing record","Scope is unclear","Delivery affected","HIGH","HIGH","Approve option A" if not source_missing else "Provide record","Which scope is approved?" if not source_missing else None,{"fields":[{"name":"scope","format":"text","example":"A","required":True}]} if not source_missing else {},source_missing,(evidence,) if not source_missing else (), (HandoverCapabilityItemRef(cap_item),), (HandoverItemOptionDraft("A","Option A"),HandoverItemOptionDraft("B","Option B")) if not source_missing else ())
                def create(item, expected):
                    return creator.create(CreateHandoverVersion(token,CSRF,uuid.uuid4(),project,analysis.handover_analysis_id,expected,(source,),baseline,cap_version,(item,),(ai_task,),str(uuid.uuid4())))
                first=create(draft(),0); second=create(draft(True),1)
                def validator(custom_audit=None):
                    return HandoverVersionValidationService(unit_of_work=runtime.unit_of_work,access=access,license_guard=guard,authorization=auth,sources=sources,evidence=evidence_port,capabilities=cap_port,ai_tasks=ai_port,repository=SqlAlchemyHandoverVersionValidationRepository(),audit_source=SqlAlchemyHandoverValidationAuditSource(),receipts=receipts,audit=custom_audit or audit)
                def validate(version,key=None,target=None):
                    return (target or validator()).validate(ValidateHandoverVersion(token,CSRF,uuid.uuid4(),project,analysis.handover_analysis_id,version.handover_analysis_version_id,key or str(uuid.uuid4())))
                pass_key=str(uuid.uuid4()); passed=validate(first,pass_key); assert passed.valid and passed.issue_codes==() and validate(first,pass_key)==passed
                action=validate(second); assert not action.valid and action.issue_codes==("ACTION_ITEM_REQUIRED",)
                with connect(name) as db:
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE' WHERE evidence_id=%s",(evidence,))
                failed=validate(first); assert not failed.valid and failed.issue_codes==("EVIDENCE_UNAVAILABLE",)
                rollback_key=str(uuid.uuid4())
                try: validate(first,rollback_key,validator(FailedAudit()))
                except Exception: pass
                else: raise AssertionError("Audit failure was not rolled back")
                recovered=validate(first,rollback_key); assert recovered.issue_codes==("EVIDENCE_UNAVAILABLE",)
                with connect(name) as db:
                    states=db.execute("SELECT array_agg(version_state ORDER BY version_no) FROM plm.hnd_analysis_versions WHERE handover_analysis_id=%s",(analysis.handover_analysis_id,)).fetchone()[0]
                    assert states==["DRAFT","DRAFT"],states
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_VERSION_VALIDATED'").fetchone()[0]==4
                print("HND_01_A03_P03_VERSION_VALIDATE_PASS: PASS replay, current Evidence failure, missing-source Action requirement, Audit rollback and zero state transition verified on PostgreSQL 18")
            finally: runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
