"""Windows 11/PostgreSQL 18 proof for Conclusion create/list/get."""

from __future__ import annotations

import importlib.util
import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionEvidenceInput, ConclusionOpenIssueInput, CreateSurveyConclusion,
    DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateError, SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.read_conclusions import (
    SurveyConclusionReadError, SurveyConclusionReadQuery,
    SurveyConclusionReadService,
)
from plm_assistant.modules.survey.infrastructure.conclusion_repository import (
    SqlAlchemySurveyConclusionRepository,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a03 = load(
    ROOT / "validation" / "sur-04-a03-conclusion-source-proofs" / "verify.py",
    "sur04a04_source_fixture",
)
auth = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
schema, definition, round_fixture = a03.schema, a03.definition, a03.round_fixture
seed_user = auth["seed_user"]
Guard, FailedAudit, CSRF = auth["Guard"], auth["FailedAudit"], auth["CSRF"]


def expect_create(code: str, action) -> None:
    try:
        action()
    except SurveyConclusionCreateError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected create failure: " + code)


def expect_read(code: str, action) -> None:
    try:
        action()
    except SurveyConclusionReadError as error:
        assert error.code == code, (error.code, code)
        return
    raise AssertionError("expected read failure: " + code)


def main() -> None:
    database = "sur04a04_" + uuid.uuid4().hex[:8]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username=USER, host=HOST, port=PORT,
            database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        with schema.connect(database) as db:
            ids = definition.seed_dependencies(db)
            pm = seed_user(db, "Conclusion PM", "NONE", pm_token)
            implementation = seed_user(
                db, "Conclusion Implementer", "NONE", impl_token,
            )
            customer = seed_user(db, "Conclusion Customer", "NONE", customer_token)
            for actor, role in (
                (pm, "PROJECT_MANAGER"),
                (implementation, "IMPLEMENTATION_MEMBER"),
                (customer, "CUSTOMER_MANAGER"),
            ):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (ids["project"], actor, ids["department"], role),
                )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion owner survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) "
                "RETURNING survey_round_id",
                (survey, version, ids["project"], pm),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s", (pm, pm, round_id),
            )
            assignment = db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING survey_assignment_id",
                (round_id, survey, version, ids["project"], ids["department"], pm),
            ).fetchone()[0]
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,),
            ).fetchone()[0]
            with db.transaction():
                response = db.execute(
                    "INSERT INTO plm.srv_responses(survey_assignment_id,"
                    "survey_round_id,survey_id,survey_version_id,project_id,"
                    "question_row_id,response_source,recorded_by,recorded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,"
                    "statement_timestamp()) RETURNING survey_response_id",
                    (assignment, round_id, survey, version, ids["project"],
                     question, pm),
                ).fetchone()[0]
                answer = db.execute(
                    "INSERT INTO plm.srv_answers(survey_response_id,"
                    "survey_assignment_id,question_row_id,project_id,raw_answer) "
                    "VALUES (%s,%s,%s,%s,'Validated actual response') "
                    "RETURNING survey_answer_id",
                    (response, assignment, question, ids["project"]),
                ).fetchone()[0]
            evidence, document, document_version, fingerprint = (
                round_fixture.insert_evidence(db, ids)
            )
            db.execute(
                "INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,"
                "survey_response_id,survey_assignment_id,question_row_id,project_id,"
                "evidence_id,document_id,document_version_id,"
                "observed_evidence_lock_version,content_fingerprint,recorded_by,"
                "recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,"
                "statement_timestamp(),0)",
                (answer, response, assignment, question, ids["project"], evidence,
                 document, document_version, fingerprint, pm),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_assignments SET submission_state='VALIDATED',"
                    "validated_by=%s,validated_at=statement_timestamp(),updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=1 "
                    "WHERE survey_assignment_id=%s", (pm, pm, assignment),
                )
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (pm, b"c" * 32, pm, round_id),
                )

            action = uuid.uuid4()
            with db.transaction():
                created = db.execute("SELECT statement_timestamp()").fetchone()[0]
                db.execute(
                    "INSERT INTO plm.hnd_action_items(action_item_id,project_id,"
                    "source_kind,source_analysis_version_ref,source_item_id,action_type,"
                    "title,requested_input_spec,owner_ref,due_at,priority,created_by,"
                    "created_reason,created_at,updated_at) VALUES (%s,%s,'ANALYSIS_ITEM',"
                    "%s,%s,'PROVIDE_INFO','Conclusion issue','{}'::jsonb,%s,"
                    "%s+interval '1 day','HIGH',%s,'A04 fixture',%s,%s)",
                    (action, ids["project"], ids["analysis_version"],
                     ids["handover_item"], pm, created, pm, created, created),
                )
                db.execute(
                    "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                    "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                    "VALUES (%s,%s,0,NULL,'OPEN',%s,'A04 fixture',%s,%s)",
                    (action, ids["project"], pm, created, uuid.uuid4()),
                )

            ai_task, invocation, suggestion = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,"
                    "requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,"
                    "context_policy_ref,task_state,suggestion_state,current_invocation_ref,"
                    "trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,"
                    "'SURVEY_ANALYZE',%s,%s,'survey-analyze.v1','survey-conclusion.v1',"
                    "'project.v1','SUCCEEDED','AVAILABLE',%s,%s,statement_timestamp(),"
                    "statement_timestamp())",
                    (ai_task, ids["project"], pm, b"i" * 32,
                     invocation, uuid.uuid4()),
                )
                db.execute(
                    "INSERT INTO plm.ai_suggestion_payloads(suggestion_payload_id,"
                    "ai_invocation_id,ai_task_id,scope,project_id,output_schema_ref,"
                    "schema_version,canonical_payload,payload_fingerprint,quality_flags) "
                    "VALUES (%s,%s,%s,'PROJECT',%s,'survey-conclusion.v1',1,%s,%s,%s)",
                    (suggestion, invocation, ai_task, ids["project"],
                     Jsonb({"summary": "non-formal draft suggestion"}),
                     b"a" * 32, Jsonb(["REVIEW_REQUIRED"])),
                )

        runtime = create_database_runtime(url)
        guard = Guard()
        guard.enabled = True
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        repository = SqlAlchemySurveyConclusionRepository()
        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(),
        )
        evidence_owner = SurveyConclusionProjectRecordProofService(
            evidence=EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=SqlAlchemyProjectAuthorizationRepository(),
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=a03.FixedDocument(facts),
                allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                }),
                required_document_category="PROJECT_RECORD",
            ),
        )
        common = dict(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
            authorization=authorization, repository=repository,
            response_owner=SqlAlchemyConclusionResponseProof(),
            evidence_owner=evidence_owner,
            issue_owner=SqlAlchemySurveyConclusionIssueProof(),
            ai_owner=SqlAlchemySurveyConclusionAITaskProof(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            clock=lambda: datetime.now(timezone.utc),
        )

        def create_service(audit=None):
            return SurveyConclusionCreateService(
                **common, audit=audit or AuditService(SqlAlchemyAuditRepository()),
            )

        def create(
            *, token=pm_token, csrf=CSRF, key=None, suffix="v1",
            supersedes=None, target=None,
        ):
            return (target or create_service()).create(CreateSurveyConclusion(
                token, csrf, uuid.uuid4(), ids["project"], survey, (round_id,),
                (DepartmentConclusionInput(
                    ids["department"], "Department " + suffix,
                    "Validated department conclusion " + suffix, (response,),
                ),),
                (ModuleConclusionInput(
                    "PLM.BOM", "Module " + suffix,
                    "Validated module conclusion " + suffix, (response,),
                ),),
                (ConclusionEvidenceInput(evidence, "SUPPORT"),),
                (ConclusionOpenIssueInput(action, True),),
                (ai_task,), supersedes, key or str(uuid.uuid4()),
            ))

        expect_create("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
        expect_create("RESOURCE_NOT_FOUND", lambda: create(token=customer_token))
        guard.enabled = False
        expect_create("LICENSE_OPERATION_DENIED", create)
        guard.enabled = True

        first_key = str(uuid.uuid4())
        first = create(key=first_key)
        replay = create(key=first_key)
        assert first == replay and first.summary.version_no == 1
        expect_create("CONFLICT_IDEMPOTENCY", lambda: create(
            key=first_key, suffix="changed",
        ))
        successor = create(suffix="v2", supersedes=first.summary.survey_conclusion_id)
        assert successor.summary.version_no == 2
        assert successor.summary.conclusion_series_id == first.summary.conclusion_series_id
        expect_create("CONCLUSION_VERSION_CONFLICT", lambda: create(
            suffix="stale", supersedes=first.summary.survey_conclusion_id,
        ))
        independent = create(token=impl_token, suffix="independent")
        assert independent.summary.version_no == 1
        assert independent.summary.conclusion_series_id != first.summary.conclusion_series_id

        concurrent_key = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(
                lambda _: create(
                    key=concurrent_key, suffix="concurrent",
                ),
                range(2),
            ))
        assert concurrent[0] == concurrent[1]

        rollback_key = str(uuid.uuid4())
        expect_create("SURVEY_CONCLUSION_UNAVAILABLE", lambda: create(
            key=rollback_key, suffix="rollback",
            target=create_service(FailedAudit()),
        ))
        recovered = create(key=rollback_key, suffix="rollback")
        assert recovered.summary.version_no == 1

        reads = SurveyConclusionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=guard,
            authorization=authorization, repository=repository,
            clock=lambda: datetime.now(timezone.utc),
        )
        customer_query = SurveyConclusionReadQuery(
            customer_token, uuid.uuid4(), ids["project"],
        )
        page1 = reads.list_conclusions(customer_query, page_size=2)
        page2 = reads.list_conclusions(
            customer_query, page_size=2,
            after_created_at=page1.next_created_at,
            after_conclusion_id=page1.next_conclusion_id,
        )
        page3 = reads.list_conclusions(
            customer_query, page_size=2,
            after_created_at=page2.next_created_at,
            after_conclusion_id=page2.next_conclusion_id,
        )
        all_ids = [item.survey_conclusion_id
                   for page in (page1, page2, page3) for item in page.items]
        assert len(all_ids) == len(set(all_ids)) == 5
        assert page1.has_more and page2.has_more and not page3.has_more
        detail = reads.get_conclusion(
            customer_query, first.summary.survey_conclusion_id,
        )
        assert len(detail.department_conclusions) == 1
        assert len(detail.module_conclusions) == 1
        assert len(detail.evidence_refs) == 1
        assert len(detail.open_issue_refs) == 1
        assert detail.evidence_refs[0].content_fingerprint == fingerprint.hex()
        assert detail.open_issue_refs[0].observed_issue_state == "OPEN"
        expect_read("RESOURCE_NOT_FOUND", lambda: reads.get_conclusion(
            SurveyConclusionReadQuery(customer_token, uuid.uuid4(), uuid.uuid4()),
            first.summary.survey_conclusion_id,
        ))

        with schema.connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.srv_conclusions",
            ).fetchone()[0] == 5
            assert db.execute(
                "SELECT array_agg(version_no ORDER BY version_no) FROM "
                "plm.srv_conclusions WHERE conclusion_series_id=%s",
                (first.summary.conclusion_series_id,),
            ).fetchone()[0] == [1, 2]
            assert db.execute(
                "SELECT count(*) FROM plm.srv_department_conclusions WHERE "
                "decision_type IS NOT NULL OR decision_evidence_id IS NOT NULL OR "
                "decision_review_ref IS NOT NULL",
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.srv_module_conclusions WHERE "
                "decision_type IS NOT NULL OR decision_evidence_id IS NOT NULL OR "
                "decision_review_ref IS NOT NULL",
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE "
                "action='SURVEY_CONCLUSION_CREATED' AND target_project_id=%s",
                (ids["project"],),
            ).fetchone()[0] == 5
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_SURVEY_CONCLUSION_CREATE'",
            ).fetchone()[0] == 5
            db.execute(
                "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                "WHERE project_id=%s AND user_id=%s",
                (ids["project"], customer),
            )
        expect_read("RESOURCE_NOT_FOUND", lambda: reads.get_conclusion(
            customer_query, first.summary.survey_conclusion_id,
        ))
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "SUR_04_A04_CONCLUSION_CREATE_READ_PASS: PM/Implementation create, "
        "typed source snapshots, Session/CSRF/License, idempotency concurrency, "
        "Audit rollback, continuous series versions, stale-parent refusal, member "
        "pagination/detail, isolation/revocation and closed formal-decision gap "
        "verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
