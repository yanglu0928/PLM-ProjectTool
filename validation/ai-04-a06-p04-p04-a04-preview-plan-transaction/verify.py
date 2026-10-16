"""Windows/PostgreSQL proof for atomic AI_TASK Preview and Content Plan."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview,
    EgressPreviewError,
    EgressPreviewPolicy,
    EgressPreviewPolicyRegistry,
    EgressPreviewService,
)
from plm_assistant.modules.ai.application.egress_task_plan import (
    AIExecutionPreviewPlanBuilder,
    AITaskPreviewPlanRequest,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef,
    AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.infrastructure.egress_preview_repository import (
    SqlAlchemyEgressPreviewRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_planning_repository import (
    SqlAlchemyAIExecutionPromptPlanningRepository,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.document.application.ai_content import DocumentAIContentService
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load_helper(directory: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def require_in_transaction(self, *_args, **_kwargs): return object()


class Inputs:
    def __init__(self, resolved): self.resolved, self.calls = resolved, 0
    def resolve_all(self, *_args, **_kwargs): self.calls += 1; return self.resolved


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit rollback")


def main() -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "content_plan_schema_helper",
    )
    document = load_helper(
        "ai-04-a06-p03-p02-a03-document-content-pg", "document_content_helper",
    )
    suffix = uuid.uuid4().hex[:10]
    database = f"ai04a06p04p04a04_{suffix}"
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    )
    scratch = Path(tempfile.mkdtemp(prefix="plm-ai-preview-plan-"))
    runtime = None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        command.upgrade(create_migration_config(url), "head")
        result_root = scratch / "results"
        result_root.mkdir()
        storage = LocalParseResultStorage(result_root)
        with schema.connect(database) as db:
            seed = schema.seed_foundation(db, suffix)
            actor, project = seed["actor"], seed["project"]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                (project, actor, department),
            )
            prompt = uuid.uuid4()
            system_text, user_text = "System {parameters}", "Input {input}"
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
                    "template_state,active_version_no,created_by) "
                    "VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)", (prompt, actor),
                )
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                    "system_template,user_template,system_template_hash,user_template_hash,"
                    "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,"
                    "created_by) VALUES (%s,1,%s,%s,%s,%s,'gap-output.v1',1,"
                    "'no-retrieval.v1','content-plan-chat.v1',%s)",
                    (prompt, system_text, user_text,
                     hashlib.sha256(system_text.encode()).hexdigest(),
                     hashlib.sha256(user_text.encode()).hexdigest(), actor),
                )
            source_bytes = "合成原始文件".encode("utf-8")
            source_sha = hashlib.sha256(source_bytes).digest()
            document_id = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                "'Atomic Preview Source','atomic.txt',%s) RETURNING document_id",
                (project, actor),
            ).fetchone()[0]
            file_id = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
                "storage_class,storage_locator,original_name_metadata,created_by,file_state,"
                "sha256,size_bytes,detected_mime,available_at) VALUES "
                "(%s,'PROJECT',%s,'PERSISTENT',%s,'atomic.txt',%s,'AVAILABLE',%s,%s,"
                "'text/plain',statement_timestamp())",
                (file_id, project, f"projects/{project.hex}/atomic.txt", actor,
                 source_sha, len(source_bytes)),
            )
            version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,%s,"
                "'text/plain',%s,%s) RETURNING document_version_id",
                (document_id, project, file_id, source_sha, len(source_bytes),
                 Jsonb({"synthetic": True}), actor),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                "WHERE document_id=%s", (version, version, document_id),
            )
            document.seed_result(
                db, storage, actor=actor, project=project, document=document_id,
                version=version, source_sha=source_sha, attempt=1,
                text="实施需求 A\r\n服务端冻结", completed_at=datetime.now(timezone.utc),
            )

        runtime = create_database_runtime(url)
        project_authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        document_owner = AIDocumentContentOwner(DocumentAIContentService(
            repository=SqlAlchemyDocumentAIContentRepository(), storage=storage,
            projects=project_authorization, license_guard=Guard(),
        ))
        task_policy = AITaskSubmissionPolicy(
            "gap-analysis.v1", 1, "GAP_ANALYSIS", prompt,
            "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
            (AITaskParameterField("language", "STRING", True, 16),),
        )
        builder = AIExecutionPreviewPlanBuilder(
            task_policies=AITaskSubmissionPolicyRegistry({
                task_policy.reference: task_policy,
            }),
            prompt_owner=AIExecutionPromptPlanningOwner(
                SqlAlchemyAIExecutionPromptPlanningRepository(),
            ),
            source_owners={"DOC-02": document_owner},
            envelope_builder=AIExecutionEnvelopeBuilder(
                renderer=StrictAIExecutionPromptRenderer(),
                context_policies=AIExecutionContextPolicyRegistry(
                    frozenset({"no-retrieval.v1"}),
                ),
                token_estimators=AIExecutionTokenEstimatorRegistry((
                    Utf8ByteUpperBoundTokenEstimator(),
                )),
            ),
        )
        plan_owner = AIExecutionContentPlanOwner(
            SqlAlchemyAIExecutionContentPlanRepository(),
        )
        public = AIInputResourceVersionRef("DOC-02", document_id, version)
        resolved = (AIResolvedInputVersionRef(
            "DOC-02", "document", "DOCUMENT_VERSION", document_id, version,
            "PROJECT", project,
        ),)
        inputs = Inputs(resolved)
        policy = EgressPreviewPolicy(
            "minimum.document.text.v1", frozenset({"AI_TASK"}),
            frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30),
            10, 131072, 131072, 3, ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        now = datetime.now(timezone.utc)

        def service(audit):
            return EgressPreviewService(
                unit_of_work=runtime.unit_of_work, access=Access(actor),
                license_guard=Guard(), authorization=Authorization(),
                input_resolver=inputs,
                policies=EgressPreviewPolicyRegistry({policy.reference: policy}),
                repository=SqlAlchemyEgressPreviewRepository(), receipts=receipts,
                audit=audit, task_plan_builder=builder,
                content_plan_owner=plan_owner, clock=lambda: now,
            )

        request = CreateEgressPreview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), project,
            "project-gap-analysis.v1", "AI_TASK", seed["provider"], seed["model"],
            (public,), ("DOCUMENT_TEXT",), "minimum.document.text.v1",
            None, 131072, 131072, 3, None,
            AITaskPreviewPlanRequest(
                "GAP_ANALYSIS", "gap-analysis.v1", "gap-output.v1",
                "no-retrieval.v1", {"language": "zh-CN"},
            ),
        )
        audit = AuditService(SqlAlchemyAuditRepository())
        first = service(audit).create(
            request, idempotency_key="A04-PREVIEW-PLAN-0001",
        )
        replay = service(audit).create(
            request, idempotency_key="A04-PREVIEW-PLAN-0001",
        )
        assert replay == first
        assert inputs.calls == 1
        with schema.connect(database) as db:
            root = db.execute(
                "SELECT p.estimated_record_count,p.payload_fingerprint,"
                "c.record_count,c.payload_fingerprint,c.payload_bytes,c.input_tokens "
                "FROM plm.ai_egress_previews p JOIN plm.ai_execution_content_plans c "
                "ON c.egress_preview_id=p.egress_preview_id "
                "WHERE p.egress_preview_id=%s", (first.preview_id,),
            ).fetchone()
            assert root is not None
            assert root[0] == root[2] == 1
            assert root[1] == root[3] == first.payload_fingerprint
            assert 1 <= root[4] <= request.max_payload_bytes
            assert 1 <= root[5] <= request.max_input_tokens
            counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                "(SELECT count(*) FROM plm.ai_execution_content_plans),"
                "(SELECT count(*) FROM plm.ai_execution_content_sources),"
                "(SELECT count(*) FROM plm.aud_events "
                " WHERE action='AI_EGRESS_PREVIEW_CREATED'),"
                "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                " WHERE operation='V1_EGRESS_PREVIEW_CREATE' AND state='COMPLETED'),"
                "(SELECT count(*) FROM plm.ai_invocations)"
            ).fetchone()
            assert counts == (1, 1, 1, 1, 1, 0), counts

        changed = CreateEgressPreview(
            request.session_token, request.csrf_token, request.trace_id,
            request.project_id, request.purpose_ref, request.operation_type,
            request.provider_id, request.model_id, request.source_refs,
            request.allowed_data_categories, request.minimal_payload_policy_ref,
            None, request.max_payload_bytes, request.max_input_tokens,
            request.max_retry_attempts, None,
            AITaskPreviewPlanRequest(
                "GAP_ANALYSIS", "gap-analysis.v1", "gap-output.v1",
                "no-retrieval.v1", {"language": "en-US"},
            ),
        )
        try:
            service(audit).create(
                changed, idempotency_key="A04-PREVIEW-PLAN-0001",
            )
        except EgressPreviewError as error:
            assert error.code == "CONFLICT_IDEMPOTENCY", error.code
        else:
            raise AssertionError("changed Task Plan replay accepted")

        try:
            service(FailingAudit()).create(
                request, idempotency_key="A04-PREVIEW-PLAN-0002",
            )
        except EgressPreviewError as error:
            assert error.code == "AI_EGRESS_PREVIEW_UNAVAILABLE", error.code
        else:
            raise AssertionError("Audit failure committed Preview/Plan")
        with schema.connect(database) as db:
            counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                "(SELECT count(*) FROM plm.ai_execution_content_plans),"
                "(SELECT count(*) FROM plm.ai_execution_content_sources),"
                "(SELECT count(*) FROM plm.ai_invocations)"
            ).fetchone()
            assert counts == (1, 1, 1, 0), counts
        print(
            "AI_04_A06_P04_P04_A04_PREVIEW_PLAN_TRANSACTION_PASS: server-derived "
            "Envelope facts, atomic Preview/Plan/Source/Audit/Receipt, exact replay, "
            "task-plan conflict and full rollback with zero provider I/O"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-ai-preview-plan-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
