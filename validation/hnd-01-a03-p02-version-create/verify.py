"""Windows 11/PostgreSQL 18 proof for complete Handover DRAFT Version creation."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.task_read_repository import SqlAlchemyAITaskReadRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.capability.infrastructure.read_repository import SqlAlchemyCapabilityReadRepository
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.handover.application.create_analysis import CreateHandoverAnalysis, HandoverAnalysisCreateService
from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, HandoverAnalysisItemDraft, HandoverCapabilityItemRef,
    HandoverItemOptionDraft, HandoverVersionCreateError, HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.source_validation import HandoverSourceValidator
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import SqlAlchemyHandoverAnalysisCreateRepository
from plm_assistant.modules.handover.infrastructure.version_create_repository import SqlAlchemyHandoverVersionCreateRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_p01_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code, action):
    try:
        action()
    except HandoverVersionCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "hnd01a03p02_" + uuid.uuid4().hex[:8]
    token = b"v" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55434, database=name)
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.downgrade(cfg, "20261005_0096")
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Handover Version PM", "NONE", token)
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('HNDV01','hndv01','Handover Version',%s) RETURNING project_id", (actor,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, department))
                    source = p01.seed_project_document(db, actor, project, "version-source")
                    evidence, baseline, cap_version, cap_item, ai_task = (uuid.uuid4() for _ in range(5))
                    cap_row = uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,document_version_id,locator_type,locator_schema_version,locator_payload,content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,'Version evidence','ELIGIBLE','fixture',%s)", (evidence, project, source.document_id, source.document_version_id, b'e'*32, actor))
                        cap_ref = "sha256:" + "a"*64
                        db.execute("INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,baseline_state,source_collection_ref,current_approved_version_ref,created_by) VALUES (%s,'HND.VERSION','Handover version','ACTIVE',%s,%s,%s)", (baseline, cap_ref, cap_version, actor))
                        db.execute("INSERT INTO plm.cap_baseline_versions(baseline_version_id,baseline_id,version_no,version_state,source_collection_ref,content_fingerprint,declared_item_count,declared_document_ref_count,declared_evidence_ref_count,created_by) VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)", (cap_version, baseline, cap_ref, b'c'*32, actor))
                        db.execute("INSERT INTO plm.cap_items(capability_item_row_id,baseline_version_id,baseline_id,capability_item_id,ordinal,capability_code,domain_name,module_name,feature_name,name,description,boundary_text,item_state) VALUES (%s,%s,%s,%s,0,'HND.VERSION.ITEM','PLM','Handover','Analysis','Analysis','Analysis capability','Project only','AVAILABLE')", (cap_row, cap_version, baseline, cap_item))
                        db.execute("INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,task_state,suggestion_state,trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap.v1','gap.output.v1','project.v1','SUCCEEDED','AVAILABLE',%s,statement_timestamp(),statement_timestamp())", (ai_task, project, actor, b'a'*32, uuid.uuid4()))
                        db.execute("INSERT INTO plm.ai_task_input_refs(input_ref_id,ai_task_id,ref_ordinal,scope,project_id,owner_module,object_type,object_id,version_id) VALUES (%s,%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)", (uuid.uuid4(), ai_task, project, source.document_id, source.document_version_id))

                authorization = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=SqlAlchemyProjectAuthorizationRepository())
                guard = Guard()
                sources = HandoverSourceValidator(SqlAlchemyDocumentReadRepository())
                audit = AuditService(SqlAlchemyAuditRepository())
                analysis_service = HandoverAnalysisCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard, authorization=authorization, sources=sources,
                    repository=SqlAlchemyHandoverAnalysisCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                    clock=lambda: datetime.now(timezone.utc),
                )
                analysis = analysis_service.create(CreateHandoverAnalysis(
                    token, CSRF, uuid.uuid4(), project, "Project handover", (source,), str(uuid.uuid4()),
                ))

                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard, authorization=authorization, sources=sources,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    capabilities=SqlAlchemyCapabilityReadRepository(),
                    ai_tasks=SqlAlchemyAITaskReadRepository(),
                    repository=SqlAlchemyHandoverVersionCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                def service(custom_audit=None):
                    return HandoverVersionCreateService(**common, audit=custom_audit or audit)
                def draft(title="Confirm scope"):
                    return HandoverAnalysisItemDraft(
                        uuid.uuid4(), "NEED_CONFIRM", title, "Scope is unclear", "Delivery affected",
                        "HIGH", "HIGH", "Approve option A", "Which scope is approved?",
                        {"fields":[{"name":"scope","format":"text","example":"A","required":True}]},
                        False, (evidence,), (HandoverCapabilityItemRef(cap_item),),
                        (HandoverItemOptionDraft("A","Option A"), HandoverItemOptionDraft("B","Option B")),
                    )
                base_item = draft()
                def create(*, expected=0, items=(base_item,), tasks=(ai_task,), key=None, target=None):
                    return (target or service()).create(CreateHandoverVersion(
                        token, CSRF, uuid.uuid4(), project, analysis.handover_analysis_id,
                        expected, (source,), baseline, cap_version, items, tasks,
                        key or str(uuid.uuid4()),
                    ))

                expect("HANDOVER_CAPABILITY_UNAVAILABLE", lambda: service().create(CreateHandoverVersion(
                    token, CSRF, uuid.uuid4(), project, analysis.handover_analysis_id, 0,
                    (source,), baseline, uuid.uuid4(), (base_item,), (), str(uuid.uuid4()),
                )))
                expect("HANDOVER_AI_PROVENANCE_UNAVAILABLE", lambda: create(tasks=(uuid.uuid4(),)))
                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(key=first_key, items=(draft("Changed"),)))
                concurrent_key = str(uuid.uuid4())
                second_item = draft("Second scope")
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(expected=1, items=(second_item,), key=concurrent_key), range(2)))
                assert results[0] == results[1] and results[0].supersedes_version_ref == first.handover_analysis_version_id
                rollback_key = str(uuid.uuid4())
                third_item = draft("Third scope")
                expect("HANDOVER_UNAVAILABLE", lambda: create(expected=2, items=(third_item,), key=rollback_key, target=service(FailedAudit())))
                recovered = create(expected=2, items=(third_item,), key=rollback_key)
                assert recovered.version_no == 3

                with connect(name) as db:
                    counts = db.execute("SELECT (SELECT count(*) FROM plm.hnd_analysis_versions),(SELECT count(*) FROM plm.hnd_analysis_source_document_refs),(SELECT count(*) FROM plm.hnd_analysis_items),(SELECT count(*) FROM plm.hnd_item_evidence_refs),(SELECT count(*) FROM plm.hnd_item_capability_refs),(SELECT count(*) FROM plm.hnd_item_options),(SELECT count(*) FROM plm.hnd_analysis_ai_task_refs)").fetchone()
                    assert counts == (3,3,3,3,3,6,3), counts
                    parent = db.execute("SELECT lock_version,current_approved_version_ref FROM plm.hnd_analyses WHERE handover_analysis_id=%s", (analysis.handover_analysis_id,)).fetchone()
                    assert parent == (3,None), parent
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='HND_VERSION_CREATED'").fetchone()[0] == 3
                try:
                    command.downgrade(cfg, "20261005_0096")
                except Exception as error:
                    assert "Handover Version history prevents downgrade" in str(error), str(error)
                else:
                    raise AssertionError("Schema0097 accepted retained Version history")
                print("HND_01_A03_P02_VERSION_CREATE_PASS: fixed Document/Capability/Evidence/AI inputs, complete NEED_CONFIRM, strong lock, replay/concurrency, Audit rollback, supersedes chain and retained-history refusal verified on PostgreSQL 18")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
