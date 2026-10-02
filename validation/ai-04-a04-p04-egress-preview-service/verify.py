"""Windows/PostgreSQL proof for internal Egress Preview create/read services."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview, EgressPreviewError, EgressPreviewPolicy,
    EgressPreviewPolicyRegistry, EgressPreviewQuery, EgressPreviewService,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
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


class Authorization:
    def require_in_transaction(self, *_args, **_kwargs): return object()


class Inputs:
    def __init__(self, resolved): self.resolved = resolved
    def resolve_all(self, *_args, **_kwargs): return self.resolved


class FailingAudit:
    def append(self, *_args, **_kwargs): raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = f"ai04a04p04_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Preview Service Owner','preview service owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGPREVSVC1','egprevsvc1','Preview Service',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGPREVSVC2','egprevsvc2','Other Preview Service',%s) RETURNING project_id",
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
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Preview Service Provider',"
                        "'endpoint.preview.service.v1',%s,'cn-beijing',"
                        "'EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-preview-service','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]

            now = datetime.now(timezone.utc)
            public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", public.resource_id,
                public.version_id, "PROJECT", project,
            ),)
            request = CreateEgressPreview(
                b"s" * 32, b"c" * 32, uuid.uuid4(), project, "gap.analysis.v1",
                "AI_TASK", provider, model, (public,), ("TECHNICAL_DOCUMENT",),
                "minimum.document.text.v1", 1, 65536, 4096, 3, b"p" * 32,
            )
            policy = EgressPreviewPolicy(
                "minimum.document.text.v1", frozenset({"AI_TASK"}),
                frozenset({"TECHNICAL_DOCUMENT"}), timedelta(minutes=30),
                10, 131072, 8192, 3, ("EXTERNAL_PROVIDER", "CUSTOMER_DATA"),
            )
            runtime = create_database_runtime(url)
            try:
                def service(audit):
                    return EgressPreviewService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(), authorization=Authorization(),
                        input_resolver=Inputs(resolved),
                        policies=EgressPreviewPolicyRegistry({policy.reference: policy}),
                        repository=SqlAlchemyEgressPreviewRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                        clock=lambda: now,
                    )

                audit = AuditService(SqlAlchemyAuditRepository())
                first = service(audit).create(request, idempotency_key="P04-PREVIEW-CREATE-0001")
                replay = service(audit).create(request, idempotency_key="P04-PREVIEW-CREATE-0001")
                assert replay == first
                assert replay.preview_fingerprint == first.preview_fingerprint
                detail = service(audit).get(
                    EgressPreviewQuery(b"s" * 32, uuid.uuid4(), project),
                    preview_id=first.preview_id,
                )
                assert detail == first
                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_egress_previews),"
                        "(SELECT count(*) FROM plm.ai_egress_preview_source_refs),"
                        "(SELECT count(*) FROM plm.aud_events "
                        " WHERE action='AI_EGRESS_PREVIEW_CREATED'),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                        " WHERE operation='V1_EGRESS_PREVIEW_CREATE' AND state='COMPLETED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1), counts
                    stored = db.execute(
                        "SELECT ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
                        "payload_fingerprint,source_refs_fingerprint FROM plm.ai_egress_previews "
                        "WHERE egress_preview_id=%s", (first.preview_id,),
                    ).fetchone()
                    assert stored[:4] == (provider, provider_config, model, "cn-beijing")
                    assert stored[4] == b"p" * 32 and len(stored[5]) == 32

                changed = CreateEgressPreview(
                    request.session_token, request.csrf_token, request.trace_id,
                    request.project_id, request.purpose_ref, request.operation_type,
                    request.provider_id, request.model_id, request.source_refs,
                    request.allowed_data_categories, request.minimal_payload_policy_ref,
                    request.estimated_record_count, 32768, request.max_input_tokens,
                    request.max_retry_attempts, request.payload_fingerprint,
                )
                try:
                    service(audit).create(changed, idempotency_key="P04-PREVIEW-CREATE-0001")
                except EgressPreviewError as error:
                    assert error.code == "CONFLICT_IDEMPOTENCY", error.code
                else:
                    raise AssertionError("changed Preview payload replay accepted")

                try:
                    service(FailingAudit()).create(
                        request, idempotency_key="P04-PREVIEW-CREATE-0002",
                    )
                except EgressPreviewError as error:
                    assert error.code == "AI_EGRESS_PREVIEW_UNAVAILABLE", error.code
                else:
                    raise AssertionError("Audit failure committed Egress Preview")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_egress_previews").fetchone()[0] == 1

                try:
                    service(audit).get(
                        EgressPreviewQuery(b"s" * 32, uuid.uuid4(), other_project),
                        preview_id=first.preview_id,
                    )
                except EgressPreviewError as error:
                    assert error.code == "RESOURCE_NOT_FOUND", error.code
                else:
                    raise AssertionError("cross-project Preview read accepted")
                print(
                    "PASS: Preview route/source proof, atomic root/source/Audit/Receipt, exact replay, "
                    "safe read, payload conflict, rollback, and project isolation"
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
