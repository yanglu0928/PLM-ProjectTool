"""Windows/PostgreSQL proof for atomic internal AI Task creation and replay."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, AITaskCreateService, AuthorizedEgressSnapshot, CreateAITask,
    input_refs_fingerprint,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import (
    SqlAlchemyAITaskCreateRepository,
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


class FailingAudit:
    def append(self, *_args, **_kwargs): raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = f"ai04a03p08_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Task Creator','synthetic task creator') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AITASKCREATE1','aitaskcreate1','Synthetic AI Task',%s) RETURNING project_id",
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
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Task Provider','endpoint.synthetic.v1',"
                        "%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-task','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]

            now = datetime.now(timezone.utc)
            public = AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4())
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", public.resource_id,
                public.version_id, "PROJECT", project,
            ),)
            auth_ref = uuid.uuid4()
            snapshot = AuthorizedEgressSnapshot(
                auth_ref, project, "gap.analysis.v1", provider, provider_config, model,
                "cn-beijing", ("TECHNICAL_DOCUMENT",), b"a" * 32, b"p" * 32,
                input_refs_fingerprint(resolved), actor, "PROJECT_MANAGER",
                now - timedelta(minutes=1), now + timedelta(hours=1),
                "document-minimal.v1", 1, 65536, 4096, 3,
                "AUTHORIZED",
            )
            command_value = CreateAITask(
                b"s" * 32, b"c" * 32, uuid.uuid4(), project, "GAP_ANALYSIS", (public,),
                "prompt.gap.v1", "schema.gap.v1", "context.gap.v1", auth_ref,
            )
            runtime = create_database_runtime(url)
            try:
                def service(audit):
                    return AITaskCreateService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(), authorization=Authorization(),
                        input_resolver=Inputs(resolved), egress_owner=Egress(snapshot),
                        repository=SqlAlchemyAITaskCreateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                        clock=lambda: now,
                    )

                audit = AuditService(SqlAlchemyAuditRepository())
                first = service(audit).create(command_value, idempotency_key="P08-TASK-CREATE-0001")
                replay = service(audit).create(command_value, idempotency_key="P08-TASK-CREATE-0001")
                assert replay == first
                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_tasks),"
                        "(SELECT count(*) FROM plm.job_jobs WHERE job_type='AI_TASK_EXECUTE'),"
                        "(SELECT count(*) FROM plm.job_outbox_events WHERE event_type='AI_TASK_QUEUED'),"
                        "(SELECT count(*) FROM plm.ai_task_input_refs),"
                        "(SELECT count(*) FROM plm.ai_egress_authorization_snapshots),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='AI_TASK_CREATED'),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                        " WHERE operation='V1_AI_TASK_CREATE' AND state='COMPLETED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1, 1, 1, 1), counts
                    assert db.execute(
                        "SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s", (first.ai_task_id,),
                    ).fetchone()[0] == first.job_id

                changed = CreateAITask(
                    command_value.session_token, command_value.csrf_token,
                    command_value.trace_id, project, "SOLUTION_SUGGEST", (public,),
                    command_value.prompt_policy_ref, command_value.output_schema_ref,
                    command_value.context_policy_ref, auth_ref,
                )
                try:
                    service(audit).create(changed, idempotency_key="P08-TASK-CREATE-0001")
                except AITaskCreateError as error:
                    assert error.code == "CONFLICT_IDEMPOTENCY", error.code
                else:
                    raise AssertionError("changed payload idempotency conflict accepted")

                try:
                    service(FailingAudit()).create(command_value, idempotency_key="P08-TASK-CREATE-0002")
                except AITaskCreateError as error:
                    assert error.code == "AI_TASK_UNAVAILABLE", error.code
                else:
                    raise AssertionError("audit failure committed AI Task")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_tasks").fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_AI_TASK_CREATE'"
                    ).fetchone()[0] == 1
                print("PASS: atomic Task/Job/Outbox/Input/Egress/Audit/Receipt, exact replay, "
                      "payload conflict, and audit failure rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
