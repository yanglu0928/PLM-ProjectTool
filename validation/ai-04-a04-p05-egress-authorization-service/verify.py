"""Windows/PostgreSQL proof for internal Egress authorize/revoke services."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.egress_authorization import (
    AuthorizeEgress, EgressAuthorizationError, EgressAuthorizationService, RevokeEgress,
)
from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview, EgressPreviewPolicy, EgressPreviewPolicyRegistry,
    EgressPreviewService,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_repository import (
    SqlAlchemyEgressAuthorizationRepository,
)
from plm_assistant.modules.ai.infrastructure.egress_preview_repository import (
    SqlAlchemyEgressPreviewRepository,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name, autocommit=True, connect_timeout=5,
    )


class Access:
    def __init__(self, actor): self.actor = actor
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class PreviewAuthorization:
    def require_in_transaction(self, *_args, **_kwargs): return object()


class ProjectAuthorization:
    def __init__(self, actor, role="PROJECT_MANAGER"):
        self.actor, self.role = actor, role
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        return AuthorizedProjectAction(user_id, project_id, operation, self.role)


class Inputs:
    def __init__(self, resolved): self.resolved = resolved
    def resolve_all(self, *_args, **_kwargs): return self.resolved


class ApprovalPolicy:
    def __init__(self, allowed=True): self.allowed = allowed
    def permits(self, *_args, **_kwargs): return self.allowed


class FailingAudit:
    def append(self, *_args, **_kwargs): raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = f"ai04a04p05_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Authorization Owner','authorization owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGAUTHSVC1','egauthsvc1','Authorization Service',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGAUTHSVC2','egauthsvc2','Other Authorization',%s) RETURNING project_id",
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
                        "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
                        "ai_provider_id,config_version_no,provider_kind,display_name,"
                        "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,"
                        "can_structured_output,can_embedding,can_rerank,created_by) VALUES "
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Authorization Service Provider',"
                        "'endpoint.authorization.service.v1',%s,'cn-beijing',"
                        "'EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-authorization-service','CHAT','rev-1','AVAILABLE',%s) "
                    "RETURNING ai_model_id", (provider, actor),
                ).fetchone()[0]

            now = datetime.now(timezone.utc)
            public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", public.resource_id,
                public.version_id, "PROJECT", project,
            ),)
            preview_policy = EgressPreviewPolicy(
                "minimum.document.text.v1", frozenset({"AI_TASK"}),
                frozenset({"TECHNICAL_DOCUMENT", "REQUIREMENT"}), timedelta(minutes=30),
                100, 131072, 8192, 3, ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
            )
            runtime = create_database_runtime(url)
            try:
                audit = AuditService(SqlAlchemyAuditRepository())
                receipts = SqlAlchemyIdempotencyReceipts()

                def preview_service():
                    return EgressPreviewService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(), authorization=PreviewAuthorization(),
                        input_resolver=Inputs(resolved),
                        policies=EgressPreviewPolicyRegistry({
                            preview_policy.reference: preview_policy,
                        }), repository=SqlAlchemyEgressPreviewRepository(),
                        receipts=receipts, audit=audit, clock=lambda: now,
                    )

                def create_preview(key: str, marker: bytes):
                    return preview_service().create(CreateEgressPreview(
                        b"s" * 32, b"c" * 32, uuid.uuid4(), project,
                        "gap.analysis.v1", "AI_TASK", provider, model, (public,),
                        ("TECHNICAL_DOCUMENT", "REQUIREMENT"),
                        "minimum.document.text.v1", 10, 65536, 4096, 3,
                        marker * 32,
                    ), idempotency_key=key)

                preview = create_preview("P05-PREVIEW-CREATE-0001", b"p")

                def service(*, policy=True, audit_service=audit, target_project=project):
                    return EgressAuthorizationService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(),
                        authorization=ProjectAuthorization(actor),
                        approval_policy=ApprovalPolicy(policy),
                        repository=SqlAlchemyEgressAuthorizationRepository(),
                        receipts=receipts, audit=audit_service, clock=lambda: now,
                    )

                authorize = AuthorizeEgress(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project,
                    preview.preview_id, preview.preview_fingerprint,
                    ("TECHNICAL_DOCUMENT",), 8, 32768, 2048, 2,
                    now + timedelta(minutes=20),
                )
                first = service().authorize(
                    authorize, idempotency_key="P05-AUTHORIZE-0001",
                )
                replay = service().authorize(
                    authorize, idempotency_key="P05-AUTHORIZE-0001",
                )
                assert replay == first and first.authorization.state == "AUTHORIZED"
                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_egress_authorizations),"
                        "(SELECT count(*) FROM plm.ai_egress_authorize_results),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='AI_EGRESS_AUTHORIZED'),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_EGRESS_AUTHORIZE' AND state='COMPLETED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1), counts

                changed = AuthorizeEgress(
                    authorize.session_token, authorize.csrf_token, authorize.trace_id,
                    authorize.project_id, authorize.preview_id,
                    authorize.expected_preview_fingerprint,
                    authorize.allowed_data_categories, 7, authorize.max_payload_bytes,
                    authorize.max_input_tokens, authorize.max_retry_attempts,
                    authorize.valid_until,
                )
                try:
                    service().authorize(changed, idempotency_key="P05-AUTHORIZE-0001")
                except EgressAuthorizationError as error:
                    assert error.code == "CONFLICT_IDEMPOTENCY", error.code
                else:
                    raise AssertionError("changed authorize replay accepted")

                denied_preview = create_preview("P05-PREVIEW-CREATE-0002", b"q")
                denied = AuthorizeEgress(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project,
                    denied_preview.preview_id, denied_preview.preview_fingerprint,
                    ("TECHNICAL_DOCUMENT",), 8, 32768, 2048, 2,
                    now + timedelta(minutes=20),
                )
                try:
                    service(policy=False).authorize(
                        denied, idempotency_key="P05-AUTHORIZE-0002",
                    )
                except EgressAuthorizationError as error:
                    assert error.code == "AI_EGRESS_APPROVAL_DENIED", error.code
                else:
                    raise AssertionError("deployment policy denial accepted")

                failing_preview = create_preview("P05-PREVIEW-CREATE-0003", b"r")
                failing = AuthorizeEgress(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project,
                    failing_preview.preview_id, failing_preview.preview_fingerprint,
                    ("TECHNICAL_DOCUMENT",), 8, 32768, 2048, 2,
                    now + timedelta(minutes=20),
                )
                try:
                    service(audit_service=FailingAudit()).authorize(
                        failing, idempotency_key="P05-AUTHORIZE-0003",
                    )
                except EgressAuthorizationError as error:
                    assert error.code == "AI_EGRESS_AUTHORIZATION_UNAVAILABLE", error.code
                else:
                    raise AssertionError("Audit failure committed Authorization")

                revoke = RevokeEgress(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project,
                    first.authorization.authorization_id, 0,
                    "USER_REQUEST", "Approval is no longer required",
                )
                revoked = service().revoke(revoke, idempotency_key="P05-REVOKE-00001")
                revoke_replay = service().revoke(
                    revoke, idempotency_key="P05-REVOKE-00001",
                )
                assert revoke_replay == revoked
                assert (revoked.state, revoked.lock_version, revoked.revoked_role) == (
                    "REVOKED", 1, "OriginalApprover",
                )
                historical = service().authorize(
                    authorize, idempotency_key="P05-AUTHORIZE-0001",
                )
                assert (historical.authorization.state,
                        historical.authorization.lock_version) == ("AUTHORIZED", 0)

                cross = RevokeEgress(
                    revoke.session_token, revoke.csrf_token, uuid.uuid4(), other_project,
                    revoke.authorization_id, 0, "USER_REQUEST", "Cross project attempt",
                )
                try:
                    service().revoke(cross, idempotency_key="P05-REVOKE-00002")
                except EgressAuthorizationError as error:
                    assert error.code == "RESOURCE_NOT_FOUND", error.code
                else:
                    raise AssertionError("cross-project revoke accepted")

                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_egress_authorizations),"
                        "(SELECT count(*) FROM plm.ai_egress_authorization_revocations),"
                        "(SELECT count(*) FROM plm.ai_egress_revoke_results),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='AI_EGRESS_REVOKED'),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_EGRESS_REVOKE' AND state='COMPLETED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1, 1), counts
                    root = db.execute(
                        "SELECT authorization_state,lock_version,allowed_data_categories,"
                        "max_record_count,max_payload_bytes,max_input_tokens,max_retry_attempts "
                        "FROM plm.ai_egress_authorizations WHERE authorization_id=%s",
                        (first.authorization.authorization_id,),
                    ).fetchone()
                    assert root == (
                        "REVOKED", 1, ["TECHNICAL_DOCUMENT"], 8, 32768, 2048, 2,
                    ), root
                print(
                    "PASS: bounded policy authorization, atomic Authorization/Audit/result/Receipt, "
                    "exact historical replay, denial/rollback, one-way revoke, and project isolation"
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
