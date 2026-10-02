"""Windows 11/PostgreSQL 18 proof of the explicit Egress HTTP composition."""

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
from plm_assistant.entrypoints.windows_ai_egress import create_windows_ai_egress_router
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy,
    EgressPreviewPolicyRegistry,
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
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.read_documents import DocumentReadService
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


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name, autocommit=True,
        connect_timeout=5,
    )


def seed_user(db: psycopg.Connection, name: str, token: bytes, csrf: bytes) -> uuid.UUID:
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (name, name.lower()),
    ).fetchone()[0]
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
    return actor


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
            and getattr(getattr(facts, "preview", None), "data_region", None) == "cn-beijing"
        )


def main() -> None:
    name = "ai04a04p08_" + uuid.uuid4().hex[:12]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            command.upgrade(create_migration_config(url), "head")
            pm_token, csrf, outsider_token = b"p" * 32, b"c" * 32, b"o" * 32
            with connect(name) as db:
                actor = seed_user(db, "Egress HTTP Project Manager", pm_token, csrf)
                seed_user(db, "Egress HTTP Outsider", outsider_token, csrf)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGHTTP1','eghttp1','Egress HTTP',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGHTTP2','eghttp2','Other Egress HTTP',%s) RETURNING project_id",
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
                    "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                    "'Egress Source','egress-source.pdf',%s) RETURNING document_id",
                    (project, actor),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES "
                    "('PROJECT',%s,'PERSISTENT',%s,'egress-source.pdf',%s,'AVAILABLE',%s,"
                    "23,'application/pdf',statement_timestamp()) RETURNING file_object_id",
                    (project, "synthetic/" + uuid.uuid4().hex, actor, b"d" * 32),
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
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) "
                    "RETURNING secret_record_id", (actor,),
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
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Egress HTTP Provider',"
                        "'endpoint.egress.http.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
                        "true,true,false,false,%s)", (config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-egress-http','CHAT','rev-1','AVAILABLE',%s) "
                    "RETURNING ai_model_id", (provider, actor),
                ).fetchone()[0]

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
            policy = EgressPreviewPolicy(
                "minimum.document.text.v1", frozenset({"AI_TASK"}),
                frozenset({"TECHNICAL_DOCUMENT"}), timedelta(minutes=30),
                10, 131072, 8192, 3,
                ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
            )
            router = create_windows_ai_egress_router(
                runtime=runtime, sessions=sessions,
                origins=LoginOriginPolicy([ORIGIN]), license_guard=guard, audit=audit,
                documents=documents,
                preview_policies=EgressPreviewPolicyRegistry({policy.reference: policy}),
                approval_policy=ApprovalPolicy(),
            )
            path = f"/api/v1/projects/{project}/egress-previews"
            headers = {
                "cookie": "plm_session=" + pm_token.hex(),
                "x-csrf-token": csrf.hex(), "origin": ORIGIN,
                "idempotency-key": str(uuid.uuid4()),
            }
            body = {
                "purpose_ref": "gap.analysis.v1", "operation_type": "AI_TASK",
                "provider_id": str(provider), "model_id": str(model),
                "source_refs": [{
                    "resource_type": "DOC-02", "resource_id": str(document),
                    "version_id": str(version),
                }],
                "allowed_data_categories": ["TECHNICAL_DOCUMENT"],
                "minimal_payload_policy_ref": "minimum.document.text.v1",
                "estimated_record_count": 1, "max_payload_bytes": 65536,
                "max_input_tokens": 4096, "max_retry_attempts": 3,
                "payload_fingerprint": (b"p" * 32).hex(),
            }
            with TestClient(create_app(), base_url=ORIGIN) as closed:
                assert closed.post(path, json=body, headers=headers).status_code == 404
            with TestClient(create_app(ai_egress_router=router), base_url=ORIGIN) as client:
                first = client.post(path, json=body, headers=headers)
                assert first.status_code == 201, first.text
                preview = first.json()["data"]
                preview_id = preview["preview_id"]
                replay = client.post(path, json=body, headers=headers)
                assert replay.status_code == 201, replay.text
                assert replay.json()["data"] == preview
                detail = client.get(
                    path + "/" + preview_id,
                    headers={"cookie": "plm_session=" + pm_token.hex()},
                )
                assert detail.status_code == 200 and detail.json()["data"] == preview
                assert client.get(
                    path + "/" + preview_id,
                    headers={"cookie": "plm_session=" + outsider_token.hex()},
                ).status_code == 404
                assert client.get(
                    f"/api/v1/projects/{other_project}/egress-previews/{preview_id}",
                    headers={"cookie": "plm_session=" + pm_token.hex()},
                ).status_code == 404
                authorize_path = path + "/" + preview_id + ":authorize"
                authorize_headers = {
                    **headers, "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
                }
                valid_until = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(
                    microsecond=0,
                ).isoformat().replace("+00:00", "Z")
                authorize_body = {
                    "expected_preview_fingerprint": preview["preview_fingerprint"],
                    "allowed_data_categories": ["TECHNICAL_DOCUMENT"],
                    "max_record_count": 1, "max_payload_bytes": 32768,
                    "max_input_tokens": 2048, "max_retry_attempts": 2,
                    "valid_until": valid_until,
                }
                approved = client.post(
                    authorize_path, json=authorize_body, headers=authorize_headers,
                )
                assert approved.status_code == 201, approved.text
                authorization = approved.json()["data"]
                assert authorization["state"] == "AUTHORIZED"
                assert client.post(
                    authorize_path, json=authorize_body, headers=authorize_headers,
                ).json()["data"] == authorization
                revoke_path = (
                    f"/api/v1/projects/{project}/egress-authorizations/"
                    f"{authorization['authorization_id']}:revoke"
                )
                revoke_headers = {
                    **headers, "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
                }
                revoke_body = {
                    "reason_code": "USER_REQUEST",
                    "reason_summary": "Synthetic composition verification completed",
                }
                revoked = client.post(revoke_path, json=revoke_body, headers=revoke_headers)
                assert revoked.status_code == 200, revoked.text
                assert revoked.json()["data"]["state"] == "REVOKED"
                assert client.post(
                    revoke_path, json=revoke_body, headers=revoke_headers,
                ).json()["data"] == revoked.json()["data"]
                historical = client.post(
                    authorize_path, json=authorize_body, headers=authorize_headers,
                )
                assert historical.status_code == 201
                assert historical.json()["data"]["state"] == "AUTHORIZED"
                guard.enabled = False
                assert client.get(
                    path + "/" + preview_id,
                    headers={"cookie": "plm_session=" + pm_token.hex()},
                ).status_code == 403
                guard.enabled = True
                assert "secret" not in first.text.lower()
                assert "traceback" not in first.text.lower()
            with connect(name) as db:
                counts = db.execute(
                    "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                    "(SELECT count(*) FROM plm.ai_egress_preview_source_refs),"
                    "(SELECT count(*) FROM plm.ai_egress_authorizations),"
                    "(SELECT count(*) FROM plm.ai_egress_authorize_results),"
                    "(SELECT count(*) FROM plm.ai_egress_authorization_revocations),"
                    "(SELECT count(*) FROM plm.ai_egress_revoke_results),"
                    "(SELECT count(*) FROM plm.aud_events WHERE action LIKE 'AI_EGRESS_%'),"
                    "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation LIKE "
                    "'V1_EGRESS_%' AND state='COMPLETED')"
                ).fetchone()
                assert counts == (1, 1, 1, 1, 1, 1, 3, 3), counts
                assert db.execute(
                    "SELECT authorization_state,lock_version FROM plm.ai_egress_authorizations"
                ).fetchone() == ("REVOKED", 1)
            print(
                "PASS: Win11 PG18 explicit Egress HTTP composition, real Session/Project/"
                "Document Owner, Preview/Authorization/Audit/Receipt persistence, replay, "
                "isolation, revoke and license denial; synthetic trust/policies, no external call"
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
