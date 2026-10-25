"""Windows 11/PostgreSQL 18 proof for authorized Handover Action creation."""

from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
from plm_assistant.modules.handover.application.create_action import (
    CreateHandoverAction, HandoverActionCreateError, HandoverActionCreateService,
)
from plm_assistant.modules.handover.application.create_analysis import CreateHandoverAnalysis, HandoverAnalysisCreateService
from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, HandoverAnalysisItemDraft, HandoverCapabilityItemRef,
    HandoverItemOptionDraft, HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.source_validation import HandoverSourceValidator
from plm_assistant.modules.handover.infrastructure.action_create_repository import SqlAlchemyHandoverActionCreateRepository
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import SqlAlchemyHandoverAnalysisCreateRepository
from plm_assistant.modules.handover.infrastructure.version_create_repository import SqlAlchemyHandoverVersionCreateRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.handover_action_assignee import SqlAlchemyHandoverActionAssigneeSource


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p01 = load(ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py", "hnd_action_fixture")
connect, seed_user, CSRF = p01.connect, p01.seed_user, p01.CSRF
Guard, FailedAudit = p01.Guard, p01.FailedAudit


def expect(code: str, action) -> None:
    try:
        action()
    except HandoverActionCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "hnd02a02_" + uuid.uuid4().hex[:9]
    pm_token, customer_token = b"p" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "Action PM", "NONE", pm_token)
                    customer = seed_user(db, "Action Customer", "NONE", customer_token)
                    disabled = seed_user(db, "Disabled Assignee", "NONE", b"d" * 32)
                    foreign_member = seed_user(db, "Foreign Assignee", "NONE", b"f" * 32)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDACT','hndact','Action Project',%s) RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    foreign_project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDFRG','hndfrg','Foreign Project',%s) RETURNING project_id", (pm,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'HND','hnd','Handover') RETURNING department_id", (project,),
                    ).fetchone()[0]
                    foreign_department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'FRG','frg','Foreign') RETURNING department_id", (foreign_project,),
                    ).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"), (customer, "CUSTOMER_MANAGER"),
                                       (disabled, "IMPLEMENTATION_MEMBER")):
                        db.execute(
                            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,%s)", (project, user, department, role),
                        )
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                        (foreign_project, foreign_member, foreign_department),
                    )
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (disabled,))
                    source = p01.seed_project_document(db, pm, project, "action-source")
                    evidence, baseline, cap_version, cap_item, ai_task = (uuid.uuid4() for _ in range(5))
                    cap_row = uuid.uuid4()
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute(
                            "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,document_id,"
                            "document_version_id,locator_type,locator_schema_version,locator_payload,"
                            "content_fingerprint,display_label,eligibility_state,eligibility_reason,created_by) "
                            "VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,'{\"locator_type\":\"DOCUMENT\"}'::jsonb,"
                            "%s,'Action evidence','ELIGIBLE','fixture',%s)",
                            (evidence, project, source.document_id, source.document_version_id, b"e" * 32, pm),
                        )
                        cap_ref = "sha256:" + "a" * 64
                        db.execute(
                            "INSERT INTO plm.cap_baselines(baseline_id,baseline_code,name,baseline_state,"
                            "source_collection_ref,current_approved_version_ref,created_by) "
                            "VALUES (%s,'HND.ACTION','Handover action','ACTIVE',%s,%s,%s)",
                            (baseline, cap_ref, cap_version, pm),
                        )
                        db.execute(
                            "INSERT INTO plm.cap_baseline_versions(baseline_version_id,baseline_id,version_no,"
                            "version_state,source_collection_ref,content_fingerprint,declared_item_count,"
                            "declared_document_ref_count,declared_evidence_ref_count,created_by) "
                            "VALUES (%s,%s,1,'APPROVED',%s,%s,1,1,1,%s)",
                            (cap_version, baseline, cap_ref, b"a" * 32, pm),
                        )
                        db.execute(
                            "INSERT INTO plm.cap_items(capability_item_row_id,baseline_version_id,baseline_id,"
                            "capability_item_id,ordinal,capability_code,domain_name,module_name,feature_name,name,"
                            "description,boundary_text,item_state) VALUES (%s,%s,%s,%s,0,'HND.ACTION.ITEM',"
                            "'PLM','Handover','Action','Action','Action capability','Project only','AVAILABLE')",
                            (cap_row, cap_version, baseline, cap_item),
                        )
                        db.execute(
                            "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
                            "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,task_state,"
                            "suggestion_state,trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,"
                            "'GAP_ANALYSIS',%s,%s,'gap.v1','gap.output.v1','project.v1','SUCCEEDED','AVAILABLE',"
                            "%s,statement_timestamp(),statement_timestamp())",
                            (ai_task, project, pm, b"t" * 32, uuid.uuid4()),
                        )
                        db.execute(
                            "INSERT INTO plm.ai_task_input_refs(input_ref_id,ai_task_id,ref_ordinal,scope,"
                            "project_id,owner_module,object_type,object_id,version_id) VALUES "
                            "(%s,%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
                            (uuid.uuid4(), ai_task, project, source.document_id, source.document_version_id),
                        )

                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                guard = Guard()
                audit = AuditService(SqlAlchemyAuditRepository())
                sources = HandoverSourceValidator(SqlAlchemyDocumentReadRepository())
                analysis = HandoverAnalysisCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard, authorization=authorization, sources=sources,
                    repository=SqlAlchemyHandoverAnalysisCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                ).create(CreateHandoverAnalysis(
                    pm_token, CSRF, uuid.uuid4(), project, "Action source", (source,), str(uuid.uuid4()),
                ))
                item_id = uuid.uuid4()
                item = HandoverAnalysisItemDraft(
                    item_id, "NEED_CONFIRM", "Confirm delivery boundary",
                    "Boundary is unclear", "Delivery acceptance is affected", "HIGH", "HIGH",
                    "Confirm one boundary", "Which boundary is approved?",
                    {"fields": [{"name": "boundary", "format": "text", "example": "A", "required": True}]},
                    True, (evidence,), (HandoverCapabilityItemRef(cap_item),),
                    (HandoverItemOptionDraft("A", "Boundary A"), HandoverItemOptionDraft("B", "Boundary B")),
                )
                version = HandoverVersionCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard, authorization=authorization, sources=sources,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    capabilities=SqlAlchemyCapabilityReadRepository(),
                    ai_tasks=SqlAlchemyAITaskReadRepository(),
                    repository=SqlAlchemyHandoverVersionCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                ).create(CreateHandoverVersion(
                    pm_token, CSRF, uuid.uuid4(), project, analysis.handover_analysis_id, 0,
                    (source,), baseline, cap_version, (item,), (ai_task,), str(uuid.uuid4()),
                ))

                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
                    license_guard=guard, authorization=authorization,
                    assignees=SqlAlchemyHandoverActionAssigneeSource(),
                    repository=SqlAlchemyHandoverActionCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                )
                def service(*, custom_guard=None, custom_audit=None):
                    values = dict(common)
                    values["license_guard"] = custom_guard or guard
                    values["audit"] = custom_audit or audit
                    return HandoverActionCreateService(**values)

                due_at = datetime.now(timezone.utc) + timedelta(days=7)
                spec = {"fields": [{
                    "name": "boundary", "format": "text", "example": "A", "required": True,
                }]}
                def create(*, token=pm_token, source_version=version.handover_analysis_version_id,
                           source_item=item_id, human=None, owner=pm, title="Confirm boundary",
                           key=None, target=None, due=due_at):
                    return (target or service()).create(CreateHandoverAction(
                        token, CSRF, uuid.uuid4(), project, source_version, source_item, human,
                        "CONFIRM_DECISION", title, spec, owner, due, "HIGH",
                        "Project manager registered a required confirmation", key or str(uuid.uuid4()),
                    ))

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(key=first_key, title="Changed title"))
                human = create(
                    source_version=None, source_item=None, human="Face-to-face project meeting",
                    title="Provide meeting attachment",
                )
                assert human.source_kind == "HUMAN" and human.human_source_reason
                expect("RESOURCE_NOT_FOUND", lambda: create(token=customer_token))
                expect("RESOURCE_NOT_FOUND", lambda: create(owner=disabled))
                expect("RESOURCE_NOT_FOUND", lambda: create(owner=foreign_member))
                expect("RESOURCE_NOT_FOUND", lambda: create(source_item=uuid.uuid4()))
                expect("VALIDATION_FAILED", lambda: create(due=datetime.now(timezone.utc) - timedelta(seconds=1)))

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    concurrent = list(pool.map(
                        lambda _: create(source_version=None, source_item=None,
                                         human="Concurrent meeting action", key=concurrent_key),
                        range(2),
                    ))
                assert concurrent[0] == concurrent[1]

                rollback_key = str(uuid.uuid4())
                expect("HANDOVER_UNAVAILABLE", lambda: create(
                    source_version=None, source_item=None, human="Audit rollback action",
                    key=rollback_key, target=service(custom_audit=FailedAudit()),
                ))
                recovered = create(
                    source_version=None, source_item=None, human="Audit rollback action",
                    key=rollback_key,
                )
                assert recovered.action_state == "OPEN"
                expired = Guard()
                expired.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: create(target=service(custom_guard=expired)))

                with connect(name) as db:
                    action_count, event_count, audit_count = db.execute(
                        "SELECT (SELECT count(*) FROM plm.hnd_action_items),"
                        "(SELECT count(*) FROM plm.hnd_action_state_events),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='HND_ACTION_CREATED')"
                    ).fetchone()
                    assert (action_count, event_count, audit_count) == (4, 4, 4), (
                        action_count, event_count, audit_count,
                    )
                    state = db.execute(
                        "SELECT item_state FROM plm.hnd_analysis_items WHERE "
                        "handover_analysis_version_id=%s AND analysis_item_id=%s",
                        (version.handover_analysis_version_id, item_id),
                    ).fetchone()[0]
                    assert state == "CANDIDATE", state
                    root = db.execute(
                        "SELECT action_state,lock_version FROM plm.hnd_action_items "
                        "WHERE action_item_id=%s", (first.action_item_id,),
                    ).fetchone()
                    assert root == ("OPEN", 0), root
                    event = db.execute(
                        "SELECT sequence_no,from_state,to_state,reason FROM plm.hnd_action_state_events "
                        "WHERE action_item_id=%s", (first.action_item_id,),
                    ).fetchone()
                    assert event == (0, None, "OPEN", first.created_reason), event
                print(
                    "HND_02_A02_ACTION_CREATE_PASS: PM authorization, current assignee, analysis/human "
                    "source, immutable OPEN event, replay/concurrency, audit rollback, License denial and "
                    "candidate non-confirmation verified on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
