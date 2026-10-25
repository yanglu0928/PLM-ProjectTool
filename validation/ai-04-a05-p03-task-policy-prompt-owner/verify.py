"""Windows/PostgreSQL proof for policy-bound AI Task Prompt snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, AITaskCreateService, AuthorizedEgressSnapshot,
    CreateAITask, input_refs_fingerprint,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskPromptOwner, AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import (
    SqlAlchemyAITaskCreateRepository,
)
from plm_assistant.modules.ai.infrastructure.task_prompt_repository import (
    SqlAlchemyAITaskPromptCurrentRepository,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def require_in_transaction(self, *_args, **_kwargs): return object()


class Inputs:
    def __init__(self, resolved): self.resolved = resolved
    def resolve_all(self, *_args, **_kwargs): return self.resolved


class Egress:
    def __init__(self, snapshot): self.snapshot = snapshot
    def resolve_authorized(self, *_args, **_kwargs): return self.snapshot


def expect(service, task, key: str, code: str) -> None:
    try:
        service.create(task, idempotency_key=key)
    except AITaskCreateError as error:
        assert error.code == code, error.code
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = f"ai04a05p03_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Prompt Task Owner','prompt task owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('PROMPTTASK1','prompttask1','Prompt Task',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                provider, provider_config = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
                        "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
                        (provider, provider_config, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions("
                        "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,"
                        "display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,"
                        "can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES "
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Prompt Task Provider','endpoint.synthetic.v1',"
                        "%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-prompt-task','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]
                prompt = uuid.uuid4()
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
                        "created_by) VALUES (%s,1,'System','User {{input}}',%s,%s,"
                        "'schema.gap.v1',1,'rag.gap.v1','provider.chat.v1',%s)",
                        (prompt, "a" * 64, "b" * 64, actor),
                    )

            now = datetime.now(timezone.utc)
            public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", public.resource_id,
                public.version_id, "PROJECT", project,
            ),)
            authorization_ref = uuid.uuid4()
            egress = AuthorizedEgressSnapshot(
                authorization_ref, project, "gap.analysis.v1", provider,
                provider_config, model, "cn-beijing", ("TECHNICAL_DOCUMENT",),
                b"a" * 32, b"p" * 32, input_refs_fingerprint(resolved), actor,
                "PROJECT_MANAGER", now - timedelta(minutes=1), now + timedelta(hours=1),
                "document-minimal.v1", 1, 65_536, 4_096, 3, "AUTHORIZED",
            )
            fields = (
                AITaskParameterField("language", "STRING", True, 16,
                                     allowed_values=("zh-CN", "en-US")),
                AITaskParameterField("max_items", "INTEGER", minimum=1, maximum=100),
                AITaskParameterField("include_evidence", "BOOLEAN"),
            )

            def policies(purpose="gap.analysis.v1", output="schema.gap.v1"):
                policy = AITaskSubmissionPolicy(
                    "prompt.gap.v1", 1, "GAP_ANALYSIS", prompt, purpose,
                    output, "rag.gap.v1", fields,
                )
                return AITaskSubmissionPolicyRegistry({policy.reference: policy})

            runtime = create_database_runtime(url)
            try:
                prompt_owner = AITaskPromptOwner(SqlAlchemyAITaskPromptCurrentRepository())
                resolved_policy = policies().resolve(
                    reference="prompt.gap.v1", task_type="GAP_ANALYSIS",
                    output_schema_ref="schema.gap.v1", context_policy_ref="rag.gap.v1",
                    parameters={"language": "zh-CN", "max_items": 50,
                                "include_evidence": True},
                )
                with runtime.unit_of_work() as tx:
                    prompt_owner.resolve_current(tx, policy=resolved_policy)

                def service(registry=None):
                    return AITaskCreateService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(), authorization=Authorization(),
                        input_resolver=Inputs(resolved), egress_owner=Egress(egress),
                        task_policies=registry or policies(),
                        prompt_owner=prompt_owner,
                        repository=SqlAlchemyAITaskCreateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=AuditService(SqlAlchemyAuditRepository()), clock=lambda: now,
                    )

                task = CreateAITask(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project, "GAP_ANALYSIS",
                    (public,), "prompt.gap.v1", "schema.gap.v1", "rag.gap.v1",
                    {"language": "zh-CN", "max_items": 50, "include_evidence": True},
                    authorization_ref,
                )
                first = service().create(task, idempotency_key="P03-TASK-00000001")
                assert service().create(task, idempotency_key="P03-TASK-00000001") == first
                with connect(name) as db:
                    row = db.execute(
                        "SELECT prompt_template_ref,prompt_version_no,task_parameters,"
                        "task_parameters_fingerprint=sha256(convert_to(task_parameters::text,'UTF8')) "
                        "FROM plm.ai_tasks WHERE ai_task_id=%s", (first.ai_task_id,),
                    ).fetchone()
                    assert row == (prompt, 1, {
                        "language": "zh-CN", "max_items": 50, "include_evidence": True,
                    }, True), row
                    assert db.execute(
                        "SELECT count(*) FROM plm.ai_tasks"
                    ).fetchone()[0] == 1

                invalid = CreateAITask(
                    task.session_token, task.csrf_token, uuid.uuid4(), project,
                    task.task_type, task.input_refs, task.prompt_policy_ref,
                    task.output_schema_ref, task.context_policy_ref,
                    {"language": "fr-FR"}, authorization_ref,
                )
                expect(service(), invalid, "P03-TASK-00000002", "AI_TASK_POLICY_INVALID")
                expect(service(policies(purpose="other.purpose.v1")), task,
                       "P03-TASK-00000003", "AI_TASK_POLICY_INVALID")
                expect(service(policies(output="schema.other.v1")), replace_output(task),
                       "P03-TASK-00000004", "AI_TASK_PROMPT_UNAVAILABLE")

                with connect(name) as db:
                    db.execute(
                        "UPDATE plm.ai_prompt_templates SET template_state='RETIRED',"
                        "lock_version=lock_version+1 WHERE prompt_template_id=%s", (prompt,),
                    )
                expect(service(), task, "P03-TASK-00000005", "AI_TASK_PROMPT_UNAVAILABLE")
                assert service().create(task, idempotency_key="P03-TASK-00000001") == first
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_tasks").fetchone()[0] == 1
                print(
                    "AI_04_A05_P03_TASK_POLICY_PROMPT_OWNER_PASS: strict typed policy, "
                    "locked ACTIVE Prompt snapshot, database JSONB fingerprint, atomic Task "
                    "persistence, historical replay and fail-closed mismatch/retirement"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def replace_output(task: CreateAITask) -> CreateAITask:
    return CreateAITask(
        task.session_token, task.csrf_token, task.trace_id, task.project_id,
        task.task_type, task.input_refs, task.prompt_policy_ref, "schema.other.v1",
        task.context_policy_ref, task.task_parameters, task.egress_authorization_ref,
    )


if __name__ == "__main__":
    main()
