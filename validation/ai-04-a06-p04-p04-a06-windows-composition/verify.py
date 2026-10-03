"""Windows 11/PostgreSQL 18 proof for planned Preview production composition.

All identities, document bytes and Prompt content are synthetic.  The proof uses
the real ASGI route, Session/Project/Document Owners and PostgreSQL transaction,
but creates no Invocation and performs no provider I/O.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_egress import create_windows_ai_egress_router
from plm_assistant.entrypoints.windows_ai_task import create_windows_ai_task_router
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry,
    EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy,
    EgressPreviewPolicyRegistry,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.application.task_execution_preflight import (
    AITaskExecutionPreflight,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_preflight_repository import (
    SqlAlchemyAITaskExecutionSnapshotRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
    SqlAlchemyDeploymentReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.session_repository import (
    SqlAlchemySessionRepository,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
ORIGIN = "https://plm.example.test"


def load_helper(directory: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_session(db, *, actor: uuid.UUID, token: bytes, csrf: bytes) -> None:
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, actor),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
        "statement_timestamp()+interval '2 hours')",
        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
    )


class Guard:
    enabled = True

    def require_valid(self, *, trace_id: uuid.UUID) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class ApprovalPolicy:
    def permits(self, _transaction: object, *, facts: object) -> bool:
        return (
            getattr(facts, "project_role", None) == "PROJECT_MANAGER"
            and getattr(getattr(facts, "preview", None), "data_region", None)
            == "cn-beijing"
        )


def main(after_validation=None) -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "composition_schema_helper",
    )
    document_helper = load_helper(
        "ai-04-a06-p03-p02-a03-document-content-pg", "composition_document_helper",
    )
    suffix = uuid.uuid4().hex[:10]
    database = f"ai04a06p04p04a06_{suffix}"
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=database,
    )
    scratch = Path(tempfile.mkdtemp(prefix="plm-ai-windows-composition-"))
    runtime = None
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        command.upgrade(create_migration_config(url), "head")
        result_root = scratch / "results"
        result_root.mkdir()
        storage = LocalParseResultStorage(result_root)
        token, csrf = b"p" * 32, b"c" * 32
        with schema.connect(database) as db:
            seed = schema.seed_foundation(db, suffix)
            actor, project = seed["actor"], seed["project"]
            seed_session(db, actor=actor, token=token, csrf=csrf)
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
            source_bytes = "合成项目需求原文".encode("utf-8")
            source_sha = hashlib.sha256(source_bytes).digest()
            document = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                "'Composition Source','composition.txt',%s) RETURNING document_id",
                (project, actor),
            ).fetchone()[0]
            file_id = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
                "storage_class,storage_locator,original_name_metadata,created_by,file_state,"
                "sha256,size_bytes,detected_mime,available_at) VALUES "
                "(%s,'PROJECT',%s,'PERSISTENT',%s,'composition.txt',%s,'AVAILABLE',%s,%s,"
                "'text/plain',statement_timestamp())",
                (file_id, project, f"projects/{project.hex}/composition.txt", actor,
                 source_sha, len(source_bytes)),
            )
            version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,%s,"
                "'text/plain',%s,%s) RETURNING document_version_id",
                (document, project, file_id, source_sha, len(source_bytes),
                 Jsonb({"synthetic": True}), actor),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                "WHERE document_id=%s", (version, version, document),
            )
            document_helper.seed_result(
                db, storage, actor=actor, project=project, document=document,
                version=version, source_sha=source_sha, attempt=1,
                text="客户需求 A\r\n服务端冻结正文",
                completed_at=datetime.now(timezone.utc),
            )

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
        task_policy = AITaskSubmissionPolicy(
            "gap-analysis.v1", 1, "GAP_ANALYSIS", prompt,
            "project-gap-analysis.v1", "gap-output.v1", "no-retrieval.v1",
            (AITaskParameterField("language", "STRING", True, 16),),
        )
        preview_policy = EgressPreviewPolicy(
            "minimum.document.text.v1", frozenset({"AI_TASK"}),
            frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30),
            10, 131072, 131072, 3, ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
        )
        task_policies = AITaskSubmissionPolicyRegistry({
            task_policy.reference: task_policy,
        })
        router = create_windows_ai_egress_router(
            runtime=runtime, sessions=sessions, origins=LoginOriginPolicy([ORIGIN]),
            license_guard=guard, audit=audit, documents=documents,
            preview_policies=EgressPreviewPolicyRegistry({
                preview_policy.reference: preview_policy,
            }),
            approval_policy=ApprovalPolicy(),
            task_policies=task_policies,
            data_root=result_root,
        )
        purposes = AITaskEgressPurposeRegistry({
            "GAP_ANALYSIS": frozenset({"project-gap-analysis.v1"}),
        })
        task_router = create_windows_ai_task_router(
            runtime=runtime, sessions=sessions, origins=LoginOriginPolicy([ORIGIN]),
            license_guard=guard, audit=audit, documents=documents,
            task_policies=task_policies, egress_purposes=purposes,
        )
        path = f"/api/v1/projects/{project}/egress-previews"
        headers = {
            "cookie": "plm_session=" + token.hex(),
            "x-csrf-token": csrf.hex(), "origin": ORIGIN,
            "idempotency-key": str(uuid.uuid4()),
        }
        body = {
            "purpose_ref": "project-gap-analysis.v1", "operation_type": "AI_TASK",
            "provider_id": str(seed["provider"]), "model_id": str(seed["model"]),
            "source_refs": [{
                "resource_type": "DOC-02", "resource_id": str(document),
                "version_id": str(version),
            }],
            "allowed_data_categories": ["DOCUMENT_TEXT"],
            "minimal_payload_policy_ref": "minimum.document.text.v1",
            "max_payload_bytes": 131072, "max_input_tokens": 131072,
            "max_retry_attempts": 3,
            "ai_task_plan": {
                "task_type": "GAP_ANALYSIS",
                "prompt_policy_ref": "gap-analysis.v1",
                "output_schema_ref": "gap-output.v1",
                "context_policy_ref": "no-retrieval.v1",
                "task_parameters": {"language": "zh-CN"},
            },
        }
        with TestClient(create_app(
            ai_egress_router=router, ai_task_create_router=task_router,
        ), base_url=ORIGIN) as client:
            first = client.post(path, json=body, headers=headers)
            assert first.status_code == 201, first.text
            preview = first.json()["data"]
            replay = client.post(path, json=body, headers=headers)
            assert replay.status_code == 201 and replay.json()["data"] == preview
            legacy = client.post(
                path,
                json={**body, "estimated_record_count": 1,
                      "payload_fingerprint": (b"p" * 32).hex()},
                headers={**headers, "idempotency-key": str(uuid.uuid4())},
            )
            assert legacy.status_code == 400, legacy.text
            authorization_headers = {
                **headers, "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
            }
            authorization = client.post(
                path + "/" + preview["preview_id"] + ":authorize",
                headers=authorization_headers,
                json={
                    "expected_preview_fingerprint": preview["preview_fingerprint"],
                    "allowed_data_categories": ["DOCUMENT_TEXT"],
                    "max_record_count": preview["estimated_record_count"],
                    "max_payload_bytes": 131072, "max_input_tokens": 131072,
                    "max_retry_attempts": 3,
                    "valid_until": (
                        datetime.now(timezone.utc) + timedelta(minutes=10)
                    ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                },
            )
            assert authorization.status_code == 201, authorization.text
            assert authorization.json()["data"]["state"] == "AUTHORIZED"
            authorization_id = authorization.json()["data"]["authorization_id"]
            task_headers = {
                **headers, "idempotency-key": str(uuid.uuid4()),
            }
            task_response = client.post(
                f"/api/v1/projects/{project}/ai-tasks",
                headers=task_headers,
                json={
                    "task_type": "GAP_ANALYSIS",
                    "input_refs": body["source_refs"],
                    "prompt_policy_ref": "gap-analysis.v1",
                    "output_schema_ref": "gap-output.v1",
                    "context_policy_ref": "no-retrieval.v1",
                    "task_parameters": {"language": "zh-CN"},
                    "egress_authorization_ref": authorization_id,
                },
            )
            assert task_response.status_code == 202, task_response.text
            task_data = task_response.json()["data"]
            assert client.post(
                f"/api/v1/projects/{project}/ai-tasks",
                headers=task_headers,
                json={
                    "task_type": "GAP_ANALYSIS",
                    "input_refs": body["source_refs"],
                    "prompt_policy_ref": "gap-analysis.v1",
                    "output_schema_ref": "gap-output.v1",
                    "context_policy_ref": "no-retrieval.v1",
                    "task_parameters": {"language": "zh-CN"},
                    "egress_authorization_ref": authorization_id,
                },
            ).json()["data"] == task_data
            preflight = AITaskExecutionPreflight(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyAITaskExecutionSnapshotRepository(),
                egress_owner=EgressAuthorizationOwner(
                    repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
                    purposes=purposes,
                ),
            )
            admitted = preflight.require(
                ai_task_id=uuid.UUID(task_data["ai_task_id"]), project_id=project,
                job_id=uuid.UUID(task_data["job_id"]), now=datetime.now(timezone.utc),
            )
            assert admitted.content_plan_ref is not None
            guard.enabled = False
            denied = client.get(
                path + "/" + preview["preview_id"],
                headers={"cookie": "plm_session=" + token.hex()},
            )
            assert denied.status_code == 403
            guard.enabled = True
            assert "secret" not in first.text.lower()
            assert "traceback" not in first.text.lower()

        with schema.connect(database) as db:
            root = db.execute(
                "SELECT p.estimated_record_count,p.payload_fingerprint,c.record_count,"
                "c.payload_fingerprint,c.provider_model_key,c.model_revision "
                "FROM plm.ai_egress_previews p JOIN plm.ai_execution_content_plans c "
                "ON c.egress_preview_id=p.egress_preview_id"
            ).fetchone()
            assert root is not None
            assert root[0] == root[2] == 1
            assert root[1] == root[3]
            assert root[4:] == ("content-plan-chat", "PROVIDER_MANAGED")
            counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                "(SELECT count(*) FROM plm.ai_egress_preview_source_refs),"
                "(SELECT count(*) FROM plm.ai_execution_content_plans),"
                "(SELECT count(*) FROM plm.ai_execution_content_sources),"
                "(SELECT count(*) FROM plm.ai_egress_authorizations),"
                "(SELECT count(*) FROM plm.aud_events WHERE action LIKE 'AI_EGRESS_%'),"
                "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                " WHERE operation LIKE 'V1_EGRESS_%' AND state='COMPLETED'),"
                "(SELECT count(*) FROM plm.ai_invocations)"
            ).fetchone()
            assert counts == (1, 1, 1, 1, 1, 2, 2, 0), counts
            links = db.execute(
                "SELECT p.content_plan_id,a.content_plan_ref,t.content_plan_ref,"
                "s.content_plan_ref FROM plm.ai_execution_content_plans p "
                "JOIN plm.ai_egress_authorizations a "
                "ON a.egress_preview_id=p.egress_preview_id "
                "JOIN plm.ai_egress_authorization_snapshots s "
                "ON s.authorization_ref=a.authorization_id "
                "JOIN plm.ai_tasks t ON t.ai_task_id=s.ai_task_id"
            ).fetchone()
            assert links is not None and len(set(links)) == 1, links
            assert admitted.content_plan_ref == links[0]
        print(
            "AI_04_A06_P04_P04_A06_WINDOWS_COMPOSITION_PASS: Win11/PostgreSQL18 "
            "real ASGI Session/Project/Document/Prompt composition created one atomic "
            "server-derived Preview+ContentPlan, exact replay, authorization and Task; "
            "Authorization/Task/Snapshot/Preflight share one PlanRef, legacy client facts "
            "rejected, License denial closed, zero Invocation/provider I/O\n"
            "AI_04_A06_P04_P05_PLAN_REF_BINDING_PASS"
        )
        if after_validation is not None:
            if not callable(after_validation):
                raise TypeError("after_validation must be callable")
            after_validation({
                "database": database,
                "url": url,
                "runtime": runtime,
                "result_root": result_root,
                "guard": guard,
                "purposes": purposes,
                "project_id": project,
                "ai_task_id": uuid.UUID(task_data["ai_task_id"]),
                "job_id": uuid.UUID(task_data["job_id"]),
            })
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
                and scratch.name.startswith("plm-ai-windows-composition-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
