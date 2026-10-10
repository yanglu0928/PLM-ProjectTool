"""Windows/PostgreSQL proof for current Authorization Owner and AI Task binding."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, AITaskCreateService, CreateAITask,
    input_refs_fingerprint,
)
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry, EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.input_resolution import (
    AIInputResourceVersionRef, AIResolvedInputVersionRef,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
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


class ProjectAuthorization:
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        return AuthorizedProjectAction(user_id, project_id, operation, "PROJECT_MANAGER")


class Inputs:
    def __init__(self, resolved): self.resolved = resolved
    def resolve_all(self, *_args, **_kwargs): return self.resolved


def main() -> None:
    name = f"ai04a04p06_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url), "head")
            now = datetime.now(timezone.utc)
            object_id, version_id = uuid.uuid4(), uuid.uuid4()
            public = AIInputResourceVersionRef("DOC-02", object_id, version_id)
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", object_id,
                version_id, "PROJECT", uuid.UUID(int=1),
            ),)
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Task Authorization Owner','task authorization owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGOWNER1','egowner1','Egress Owner',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EGOWNER2','egowner2','Other Egress Owner',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                resolved = (AIResolvedInputVersionRef(
                    "DOC-02", "document", "DOCUMENT_VERSION", object_id,
                    version_id, "PROJECT", project,
                ),)
                source_fingerprint = input_refs_fingerprint(resolved)
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
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Task Owner Provider',"
                        "'endpoint.task.owner.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
                        "true,true,false,false,%s)",
                        (provider_config, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,model_state,created_by) VALUES "
                    "(%s,'chat-task-owner','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]
                preview = db.execute(
                    "INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,"
                    "ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
                    "allowed_data_categories,minimal_payload_policy_ref,estimated_record_count,"
                    "max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,"
                    "source_refs_fingerprint,risk_codes,created_by,trace_id,expires_at) VALUES "
                    "('PROJECT',%s,'gap.analysis.v1','AI_TASK',%s,%s,%s,'cn-beijing',%s,"
                    "'minimum.document.text.v1',10,65536,4096,3,%s,%s,%s,%s,%s,"
                    "statement_timestamp()+interval '30 minutes') RETURNING egress_preview_id",
                    (project, provider, provider_config, model,
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32, source_fingerprint,
                     Jsonb(["EXTERNAL_PROVIDER"]), actor, uuid.uuid4()),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,ref_ordinal,"
                    "resource_type,owner_module,object_type,object_id,version_id,scope,project_id) "
                    "VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',%s,%s,'PROJECT',%s)",
                    (preview, object_id, version_id, project),
                )
                trace = uuid.uuid4()
                authorization_id = uuid.uuid4()
                with db.transaction():
                    authorization = db.execute(
                        "INSERT INTO plm.ai_egress_authorizations(authorization_id,egress_preview_id,"
                        "scope,project_id,purpose_ref,operation_type,ai_provider_id,"
                        "provider_config_version_id,ai_model_id,data_region,allowed_data_categories,"
                        "minimal_payload_policy_ref,max_record_count,max_payload_bytes,"
                        "max_input_tokens,max_retry_attempts,payload_fingerprint,"
                        "source_refs_fingerprint,approved_by,approved_role,valid_until) VALUES "
                        "(%s,%s,'PROJECT',%s,'gap.analysis.v1','AI_TASK',%s,%s,%s,'cn-beijing',"
                        "%s,'minimum.document.text.v1',8,32768,2048,2,%s,%s,%s,'ProjectManager',"
                        "statement_timestamp()+interval '20 minutes') "
                        "RETURNING approved_at,valid_until",
                        (authorization_id, preview, project, provider, provider_config, model,
                         Jsonb(["TECHNICAL_DOCUMENT"]), b"p" * 32,
                         source_fingerprint, actor),
                    ).fetchone()
                    audit_id = db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                        "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
                        "target_object_id) VALUES (%s,'PROJECT',%s,'USER',%s,"
                        "'AI_EGRESS_AUTHORIZED','SUCCESS','ai','AI-04',%s) "
                        "RETURNING audit_event_id",
                        (trace, project, actor, authorization_id),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.ai_egress_authorize_results(result_id,authorization_id,"
                        "egress_preview_id,actor_id,approved_role,audit_event_id,trace_id,"
                        "result_state,lock_version,approved_at,valid_until) VALUES "
                        "(%s,%s,%s,%s,'ProjectManager',%s,%s,'AUTHORIZED',0,%s,%s)",
                        (uuid.uuid4(), authorization_id, preview, actor, audit_id, trace,
                         authorization[0], authorization[1]),
                    )

            now = datetime.now(timezone.utc)
            runtime = create_database_runtime(url)
            try:
                receipts = SqlAlchemyIdempotencyReceipts()
                owner = EgressAuthorizationOwner(
                    repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
                    purposes=AITaskEgressPurposeRegistry({
                        "GAP_ANALYSIS": frozenset({"gap.analysis.v1"}),
                    }),
                )

                def task_service(current_inputs=resolved, clock_now=now):
                    return AITaskCreateService(
                        unit_of_work=runtime.unit_of_work, access=Access(actor),
                        license_guard=Guard(), authorization=ProjectAuthorization(),
                        input_resolver=Inputs(current_inputs), egress_owner=owner,
                        repository=SqlAlchemyAITaskCreateRepository(), receipts=receipts,
                        audit=AuditService(SqlAlchemyAuditRepository()),
                        clock=lambda: clock_now,
                    )

                task = CreateAITask(
                    b"s" * 32, b"c" * 32, uuid.uuid4(), project, "GAP_ANALYSIS",
                    (public,), "gap.prompt.v1", "gap.output.v1", "rag.context.v1",
                    authorization_id,
                )
                first = task_service().create(task, idempotency_key="P06-AI-TASK-CREATE-0001")
                replay = task_service().create(task, idempotency_key="P06-AI-TASK-CREATE-0001")
                assert replay == first
                with connect(name) as db:
                    counts = db.execute(
                        "SELECT (SELECT count(*) FROM plm.ai_tasks),"
                        "(SELECT count(*) FROM plm.ai_task_input_refs),"
                        "(SELECT count(*) FROM plm.ai_egress_authorization_snapshots),"
                        "(SELECT count(*) FROM plm.job_jobs WHERE owner_module='ai' "
                        "AND job_type='AI_TASK_EXECUTE'),"
                        "(SELECT count(*) FROM plm.job_outbox_events "
                        "WHERE event_type='AI_TASK_QUEUED'),"
                        "(SELECT count(*) FROM plm.aud_events WHERE action='AI_TASK_CREATED'),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts "
                        "WHERE operation='V1_AI_TASK_CREATE' AND state='COMPLETED')"
                    ).fetchone()
                    assert counts == (1, 1, 1, 1, 1, 1, 1), counts
                    snapshot = db.execute(
                        "SELECT authorization_ref,source_refs_fingerprint,approved_role,"
                        "authorization_state_at_capture,max_payload_bytes,max_input_tokens,"
                        "max_retry_attempts,octet_length(authorization_fingerprint) "
                        "FROM plm.ai_egress_authorization_snapshots WHERE ai_task_id=%s",
                        (first.ai_task_id,),
                    ).fetchone()
                    assert snapshot == (
                        authorization_id, source_fingerprint, "PROJECT_MANAGER",
                        "AUTHORIZED", 32768, 2048, 2, 32,
                    ), snapshot

                wrong_resolved = (AIResolvedInputVersionRef(
                    "DOC-02", "document", "DOCUMENT_VERSION", object_id,
                    uuid.uuid4(), "PROJECT", project,
                ),)
                wrong_task = CreateAITask(
                    task.session_token, task.csrf_token, uuid.uuid4(), project,
                    task.task_type, (AIInputResourceVersionRef(
                        "DOC-02", object_id, wrong_resolved[0].version_id,
                    ),), task.prompt_policy_ref, task.output_schema_ref,
                    task.context_policy_ref, authorization_id,
                )
                try:
                    task_service(wrong_resolved).create(
                        wrong_task, idempotency_key="P06-AI-TASK-CREATE-0002",
                    )
                except AITaskCreateError as error:
                    assert error.code == "AI_EGRESS_AUTHORIZATION_INVALID", error.code
                else:
                    raise AssertionError("mismatched source set accepted")

                try:
                    task_service(clock_now=now + timedelta(hours=1)).create(
                        task, idempotency_key="P06-AI-TASK-CREATE-0003",
                    )
                except AITaskCreateError as error:
                    assert error.code == "AI_EGRESS_AUTHORIZATION_INVALID", error.code
                else:
                    raise AssertionError("expired authorization accepted")

                with connect(name) as db, db.transaction():
                    revoke_trace = uuid.uuid4()
                    revoke_audit = db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                        "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
                        "target_object_id) VALUES (%s,'PROJECT',%s,'USER',%s,"
                        "'AI_EGRESS_REVOKED','SUCCESS','ai','AI-04',%s) "
                        "RETURNING audit_event_id",
                        (revoke_trace, project, actor, authorization_id),
                    ).fetchone()[0]
                    revocation = db.execute(
                        "INSERT INTO plm.ai_egress_authorization_revocations(authorization_id,"
                        "revoked_by,revoked_role,reason_code,reason_summary,audit_event_id,trace_id) "
                        "VALUES (%s,%s,'OriginalApprover','USER_REQUEST','Task owner proof',%s,%s) "
                        "RETURNING revocation_id,revoked_at",
                        (authorization_id, actor, revoke_audit, revoke_trace),
                    ).fetchone()
                    db.execute(
                        "UPDATE plm.ai_egress_authorizations SET authorization_state='REVOKED',"
                        "lock_version=1 WHERE authorization_id=%s", (authorization_id,),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_egress_revoke_results(result_id,authorization_id,"
                        "revocation_id,actor_id,revoked_role,audit_event_id,trace_id,result_state,"
                        "lock_version,revoked_at) VALUES (%s,%s,%s,%s,'OriginalApprover',%s,%s,"
                        "'REVOKED',1,%s)",
                        (uuid.uuid4(), authorization_id, revocation[0], actor,
                         revoke_audit, revoke_trace, revocation[1]),
                    )
                try:
                    task_service().create(task, idempotency_key="P06-AI-TASK-CREATE-0004")
                except AITaskCreateError as error:
                    assert error.code == "AI_EGRESS_AUTHORIZATION_INVALID", error.code
                else:
                    raise AssertionError("revoked authorization accepted for new Task")
                assert task_service().create(
                    task, idempotency_key="P06-AI-TASK-CREATE-0001",
                ) == first

                cross = CreateAITask(
                    task.session_token, task.csrf_token, uuid.uuid4(), other_project,
                    task.task_type, task.input_refs, task.prompt_policy_ref,
                    task.output_schema_ref, task.context_policy_ref, authorization_id,
                )
                try:
                    task_service().create(cross, idempotency_key="P06-AI-TASK-CREATE-0005")
                except AITaskCreateError as error:
                    assert error.code == "AI_EGRESS_AUTHORIZATION_INVALID", error.code
                else:
                    raise AssertionError("cross-project Authorization accepted")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_tasks").fetchone()[0] == 1
                print(
                    "PASS: live Authorization Owner projection, purpose/source/expiry/revocation/"
                    "project guards, atomic Task snapshot, and historical Task replay"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}" ).format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
