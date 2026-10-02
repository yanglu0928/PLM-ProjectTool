"""Windows 11/PostgreSQL 18 proof for production Task HTTP and execution preflight."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.ai_task_policy import create_deployment_ai_task_policies
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_egress import create_windows_ai_egress_router
from plm_assistant.entrypoints.windows_ai_task import create_windows_ai_task_router
from plm_assistant.modules.ai.application.egress_authorization_owner import EgressAuthorizationOwner
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy, EgressPreviewPolicyRegistry,
)
from plm_assistant.modules.ai.application.task_execution_preflight import (
    AITaskExecutionPreflight, AITaskExecutionPreflightError,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_preflight_repository import (
    SqlAlchemyAITaskExecutionSnapshotRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
ORIGIN = "https://plm.example.test"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


class Guard:
    def require_valid(self, **_kwargs):
        return object()


class ApprovalPolicy:
    def permits(self, _transaction: object, *, facts: object) -> bool:
        return (
            getattr(facts, "project_role", None) == "PROJECT_MANAGER"
            and getattr(getattr(facts, "preview", None), "data_region", None)
            == "cn-beijing"
        )


def main() -> None:
    name = "ai04a05p05_" + uuid.uuid4().hex[:12]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            command.upgrade(create_migration_config(url), "head")
            command.downgrade(create_migration_config(url), "20261003_0070")
            command.upgrade(create_migration_config(url), "head")
            token, csrf = b"s" * 32, b"c" * 32
            now = datetime.now(timezone.utc).replace(microsecond=0)
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Task HTTP Manager','task http manager') RETURNING user_id"
                ).fetchone()[0]
                credential = db.execute(
                    "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
                    "password_hash,algorithm_id,parameter_set) VALUES "
                    "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
                    "RETURNING password_credential_id", (actor,),
                ).fetchone()[0]
                db.execute(
                    "UPDATE plm.auth_users SET credential_version=1,"
                    "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                    (credential, actor),
                )
                db.execute(
                    "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
                    "credential_version,idle_expires_at,absolute_expires_at) VALUES "
                    "(%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
                    "statement_timestamp()+interval '2 hours')",
                    (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
                )
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('TASKHTTP1','taskhttp1','Task HTTP',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                department = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                    "project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                    (project, actor, department),
                )
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                    "original_display_name,created_by) VALUES "
                    "('PROJECT',%s,'PROJECT_RECORD','Task Input','task-input.pdf',%s) "
                    "RETURNING document_id", (project, actor),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES "
                    "('PROJECT',%s,%s,%s,'task-input.pdf',%s,'AVAILABLE',%s,23,"
                    "'application/pdf',statement_timestamp()) RETURNING file_object_id",
                    (project, "PERSISTENT", "synthetic/" + uuid.uuid4().hex,
                     actor, b"d" * 32),
                ).fetchone()[0]
                version = db.execute(
                    "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
                    "file_object_id,content_sha256,size_bytes,detected_mime,created_by) VALUES "
                    "(%s,'PROJECT',%s,1,%s,%s,23,'application/pdf',%s) "
                    "RETURNING document_version_id",
                    (document, project, file_id, b"d" * 32, actor),
                ).fetchone()[0]
                db.execute(
                    "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                    "WHERE document_id=%s", (version, version, document),
                )
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                provider, config = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
                        "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
                        (provider, config, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
                        "ai_provider_id,config_version_no,provider_kind,display_name,"
                        "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,"
                        "can_structured_output,can_embedding,can_rerank,created_by) VALUES "
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Task HTTP Provider',"
                        "'endpoint.synthetic.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
                        "true,true,false,false,%s)", (config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-task-http','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
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
                        "'gap-analysis-output.v1',1,'project-documents.v1',"
                        "'provider.chat.v1',%s)", (prompt, "a" * 64, "b" * 64, actor),
                    )
            with tempfile.TemporaryDirectory() as data_root:
                settings = BootstrapSettings(
                    data_root=Path(data_root),
                    ai_task_policies=({
                        "reference": "gap-analysis.v1", "policy_version": 1,
                        "task_type": "GAP_ANALYSIS", "prompt_template_id": str(prompt),
                        "purpose_ref": "project-gap-analysis.v1",
                        "output_schema_ref": "gap-analysis-output.v1",
                        "context_policy_ref": "project-documents.v1",
                        "parameter_fields": ({
                            "name": "language", "value_type": "STRING", "required": True,
                            "max_length": 16, "minimum": None, "maximum": None,
                            "allowed_values": ("zh-CN", "en-US"),
                        },),
                    },),
                )
                task_policies, purposes = create_deployment_ai_task_policies(settings)
                runtime = create_database_runtime(url)
                guard = Guard()
                audit = AuditService(SqlAlchemyAuditRepository())
                sessions = SessionService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit,
                )
                documents = DocumentReadService(
                    unit_of_work=runtime.unit_of_work,
                    session_access=SqlAlchemyProjectReadAccess(),
                    admin_access=SqlAlchemyDeploymentReadAccess(),
                    project_facts=SqlAlchemyProjectAuthorizationRepository(),
                    license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
                )
                origins = LoginOriginPolicy([ORIGIN])
                task_router = create_windows_ai_task_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=documents,
                    task_policies=task_policies, egress_purposes=purposes,
                )
                preview_policy = EgressPreviewPolicy(
                    "minimum-document-text.v1", frozenset({"AI_TASK"}),
                    frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30),
                    10, 65_536, 4_096, 2, ("EXTERNAL_PROVIDER",),
                )
                egress_router = create_windows_ai_egress_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, documents=documents,
                    preview_policies=EgressPreviewPolicyRegistry({
                        preview_policy.reference: preview_policy,
                    }),
                    approval_policy=ApprovalPolicy(),
                )
                path = f"/api/v1/projects/{project}/ai-tasks"
                headers = {
                    "cookie": "plm_session=" + token.hex(), "x-csrf-token": csrf.hex(),
                    "origin": ORIGIN, "idempotency-key": str(uuid.uuid4()),
                }
                with TestClient(create_app(), base_url=ORIGIN) as closed:
                    assert closed.post(path, json={}, headers=headers).status_code == 404
                with TestClient(create_app(
                    ai_egress_router=egress_router,
                    ai_task_create_router=task_router,
                ), base_url=ORIGIN) as client:
                    input_refs = [{"resource_type": "DOC-02",
                                   "resource_id": str(document),
                                   "version_id": str(version)}]
                    preview_headers = {**headers, "idempotency-key": str(uuid.uuid4())}
                    preview_path = f"/api/v1/projects/{project}/egress-previews"
                    preview_response = client.post(preview_path, headers=preview_headers, json={
                        "purpose_ref": "project-gap-analysis.v1",
                        "operation_type": "AI_TASK", "provider_id": str(provider),
                        "model_id": str(model), "source_refs": input_refs,
                        "allowed_data_categories": ["DOCUMENT_TEXT"],
                        "minimal_payload_policy_ref": "minimum-document-text.v1",
                        "estimated_record_count": 1, "max_payload_bytes": 65_536,
                        "max_input_tokens": 4_096, "max_retry_attempts": 2,
                        "payload_fingerprint": (b"p" * 32).hex(),
                    })
                    assert preview_response.status_code == 201, preview_response.text
                    preview_data = preview_response.json()["data"]
                    authorize_headers = {
                        **headers, "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
                    }
                    authorize_response = client.post(
                        preview_path + f"/{preview_data['preview_id']}:authorize",
                        headers=authorize_headers, json={
                            "expected_preview_fingerprint": preview_data["preview_fingerprint"],
                            "allowed_data_categories": ["DOCUMENT_TEXT"],
                            "max_record_count": 1, "max_payload_bytes": 32_768,
                            "max_input_tokens": 2_048, "max_retry_attempts": 2,
                            "valid_until": (datetime.now(timezone.utc) + timedelta(minutes=20))
                            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                        },
                    )
                    assert authorize_response.status_code == 201, authorize_response.text
                    authorization = uuid.UUID(
                        authorize_response.json()["data"]["authorization_id"]
                    )
                    body = {
                        "task_type": "GAP_ANALYSIS", "input_refs": input_refs,
                        "prompt_policy_ref": "gap-analysis.v1",
                        "output_schema_ref": "gap-analysis-output.v1",
                        "context_policy_ref": "project-documents.v1",
                        "task_parameters": {"language": "zh-CN"},
                        "egress_authorization_ref": str(authorization),
                    }
                    headers = {**headers, "idempotency-key": str(uuid.uuid4())}
                    created = client.post(path, json=body, headers=headers)
                    assert created.status_code == 202, created.text
                    data = created.json()["data"]
                    task_id, job_id = uuid.UUID(data["ai_task_id"]), uuid.UUID(data["job_id"])
                    replay = client.post(path, json=body, headers=headers)
                    assert replay.status_code == 202 and replay.json()["data"] == data

                    preflight = AITaskExecutionPreflight(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyAITaskExecutionSnapshotRepository(),
                        egress_owner=EgressAuthorizationOwner(
                            repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
                            purposes=purposes,
                        ),
                    )
                    admitted = preflight.require(
                        ai_task_id=task_id, project_id=project, job_id=job_id,
                        now=datetime.now(timezone.utc),
                    )
                    assert admitted.prompt_policy_version == 1
                    assert admitted.task_parameters == {"language": "zh-CN"}

                    with connect(name) as db:
                        row = db.execute(
                            "SELECT prompt_policy_version,prompt_template_ref,prompt_version_no,"
                            "task_parameters_fingerprint=sha256(convert_to(task_parameters::text,'UTF8')) "
                            "FROM plm.ai_tasks WHERE ai_task_id=%s", (task_id,),
                        ).fetchone()
                        assert row == (1, prompt, 1, True), row
                        try:
                            db.execute(
                                "UPDATE plm.ai_tasks SET prompt_policy_version=2 "
                                "WHERE ai_task_id=%s", (task_id,),
                            )
                        except psycopg.Error:
                            pass
                        else:
                            raise AssertionError("policy version mutation was accepted")
                    revoke_response = client.post(
                        f"/api/v1/projects/{project}/egress-authorizations/"
                        f"{authorization}:revoke",
                        headers={**headers, "idempotency-key": str(uuid.uuid4()),
                                 "if-match": '"v0"'},
                        json={"reason_code": "USER_REQUEST",
                              "reason_summary": "Execution preflight revocation proof"},
                    )
                    assert revoke_response.status_code == 200, revoke_response.text
                    try:
                        preflight.require(
                            ai_task_id=task_id, project_id=project, job_id=job_id,
                            now=datetime.now(timezone.utc),
                        )
                    except AITaskExecutionPreflightError:
                        pass
                    else:
                        raise AssertionError("revoked authorization was admitted")
                    denied_headers = {**headers, "idempotency-key": str(uuid.uuid4())}
                    assert client.post(path, json=body, headers=denied_headers).status_code == 403
                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_tasks),"
                        "(SELECT count(*) FROM plm.job_jobs WHERE owner_module='ai' "
                        "AND job_type='AI_TASK_EXECUTE'),"
                        "(SELECT count(*) FROM plm.ai_egress_authorization_snapshots),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='AI_TASK_CREATED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1), counts
                runtime.dispose()
                runtime = None
                try:
                    command.downgrade(create_migration_config(url), "20261003_0070")
                except Exception:
                    pass
                else:
                    raise AssertionError("populated policy-version history allowed downgrade")
                with connect(name) as db:
                    assert db.execute(
                        "SELECT version_num FROM plm.alembic_version"
                    ).fetchone()[0] == "20261003_0071"
            print(
                "AI_04_A05_P05_TASK_PRODUCTION_PREFLIGHT_PASS: Windows 11, PostgreSQL 18, "
                "explicit non-secret deployment policy, real Session/Project/Document/Egress "
                "Owners, empty up/down/re-up, populated downgrade refusal, HTTP 202/replay, "
                "policy-version immutability, execution admission and revocation denial; "
                "no external Provider call"
            )
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
