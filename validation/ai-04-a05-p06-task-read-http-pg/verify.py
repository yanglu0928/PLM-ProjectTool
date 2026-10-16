"""Windows 11/PostgreSQL 18 proof for authorized AI Task metadata GET."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_task_read import create_windows_ai_task_read_router
from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateService, AuthorizedEgressSnapshot, CreateAITask, input_refs_fingerprint,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskPromptOwner, AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import SqlAlchemyAITaskCreateRepository
from plm_assistant.modules.ai.infrastructure.task_prompt_repository import SqlAlchemyAITaskPromptCurrentRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
ORIGIN = "https://plm.example.test"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


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


def seed_user(db, display, normalized, token, csrf):
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (display, normalized),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,"
        "algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY',"
        "'{}'::jsonb) RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, actor),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) VALUES "
        "(%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
        "statement_timestamp()+interval '2 hours')",
        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
    )
    return actor


def main():
    name = "ai04a05p06_" + uuid.uuid4().hex[:12]
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            command.upgrade(create_migration_config(url), "head")
            csrf = b"c" * 32
            requester_token, manager_token, member_token = b"r" * 32, b"m" * 32, b"o" * 32
            with connect(name) as db:
                requester = seed_user(db, "Task Requester", "task requester", requester_token, csrf)
                manager = seed_user(db, "Task Manager", "task manager", manager_token, csrf)
                member = seed_user(db, "Task Member", "task member", member_token, csrf)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('TASKREAD1','taskread1','Task Read',%s) RETURNING project_id",
                    (manager,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('TASKREAD2','taskread2','Other Task Read',%s) RETURNING project_id",
                    (manager,),
                ).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                for actor, role in ((requester, "IMPLEMENTATION_MEMBER"),
                                    (manager, "PROJECT_MANAGER"),
                                    (member, "CUSTOMER_MEMBER")):
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                        "project_role) VALUES (%s,%s,%s,%s)",
                        (project, actor, department, role),
                    )
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (manager,),
                ).fetchone()[0]
                provider, config = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
                        "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
                        (provider, config, manager),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
                        "ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,"
                        "secret_ref,data_region,egress_class,can_chat,can_structured_output,"
                        "can_embedding,can_rerank,created_by) VALUES (%s,%s,1,'OPENAI_COMPATIBLE',"
                        "'Task Read Provider','endpoint.synthetic.v1',%s,'cn-beijing',"
                        "'EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                        (config, provider, secret, manager),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-task-read','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, manager),
                ).fetchone()[0]
                prompt = uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
                        "template_state,active_version_no,created_by) "
                        "VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)", (prompt, manager),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                        "system_template,user_template,system_template_hash,user_template_hash,"
                        "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,created_by) "
                        "VALUES (%s,1,'System secret text','User secret text',%s,%s,"
                        "'gap-output.v1',1,'project-documents.v1','provider.chat.v1',%s)",
                        (prompt, "a" * 64, "b" * 64, manager),
                    )

            document, version = uuid.uuid4(), uuid.uuid4()
            public = AIInputResourceVersionRef("DOC-02", document, version)
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", document, version,
                "PROJECT", project,
            ),)
            now = datetime.now(timezone.utc)
            authorization_ref = uuid.uuid4()
            egress = AuthorizedEgressSnapshot(
                authorization_ref, project, "project-gap-analysis.v1", provider, config,
                model, "cn-beijing", ("DOCUMENT_TEXT",), b"a" * 32, b"p" * 32,
                input_refs_fingerprint(resolved), manager, "PROJECT_MANAGER",
                now - timedelta(minutes=1), now + timedelta(minutes=30),
                "document-minimal.v1", 1, 65_536, 4_096, 2, "AUTHORIZED",
            )
            policy = AITaskSubmissionPolicy(
                "gap-analysis.v1", 7, "GAP_ANALYSIS", prompt,
                "project-gap-analysis.v1", "gap-output.v1", "project-documents.v1",
                (AITaskParameterField("language", "STRING", True, 16,
                                      allowed_values=("zh-CN",)),),
            )
            runtime = create_database_runtime(url)
            task = AITaskCreateService(
                unit_of_work=runtime.unit_of_work, access=Access(requester),
                license_guard=Guard(), authorization=Authorization(),
                input_resolver=Inputs(resolved), egress_owner=Egress(egress),
                task_policies=AITaskSubmissionPolicyRegistry({policy.reference: policy}),
                prompt_owner=AITaskPromptOwner(SqlAlchemyAITaskPromptCurrentRepository()),
                repository=SqlAlchemyAITaskCreateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                audit=AuditService(SqlAlchemyAuditRepository()), clock=lambda: now,
            ).create(CreateAITask(
                b"s" * 32, b"c" * 32, uuid.uuid4(), project, "GAP_ANALYSIS",
                (public,), policy.reference, policy.output_schema_ref,
                policy.context_policy_ref, {"language": "zh-CN"}, authorization_ref,
            ), idempotency_key="P06-TASK-READ-0001")
            router = create_windows_ai_task_read_router(
                runtime=runtime, origins=LoginOriginPolicy([ORIGIN]), license_guard=Guard(),
            )
            path = f"/api/v1/projects/{project}/ai-tasks/{task.ai_task_id}"
            headers = lambda token: {"cookie": "plm_session=" + token.hex(),
                                     "host": "plm.example.test"}
            with TestClient(create_app(ai_task_read_router=router), base_url=ORIGIN) as client:
                requester_response = client.get(path, headers=headers(requester_token))
                manager_response = client.get(path, headers=headers(manager_token))
                assert requester_response.status_code == manager_response.status_code == 200
                data = requester_response.json()["data"]
                assert data["prompt_policy_version"] == 7
                assert data["prompt_version_ref"] == {
                    "prompt_template_id": str(prompt), "version_no": 1,
                }
                assert data["input_refs"] == [{
                    "resource_type": "DOC-02", "resource_id": str(document),
                    "version_id": str(version),
                }]
                assert data["job_id"] == str(task.job_id)
                assert "task_parameters" not in data and "secret text" not in requester_response.text
                assert client.get(path, headers=headers(member_token)).status_code == 404
                assert client.get(
                    f"/api/v1/projects/{other_project}/ai-tasks/{task.ai_task_id}",
                    headers=headers(manager_token),
                ).status_code == 404
                assert client.get(path + "?raw=true", headers=headers(requester_token)).status_code == 400
            print(
                "AI_04_A05_P06_TASK_READ_HTTP_PG_PASS: Windows 11, PostgreSQL 18, "
                "requester/manager authorized metadata, ordinary-member and cross-project "
                "404 isolation, policy/Prompt/input/authorization/Job refs, no parameters or text"
            )
        finally:
            if runtime is not None: runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__": main()
