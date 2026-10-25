"""Windows 11/PostgreSQL 18 proof for complete non-content execution grants."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import input_refs_fingerprint
from plm_assistant.modules.ai.application.egress_authorization import EgressAuthorizationView
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry, EgressAuthorizationOwner,
    authorization_fingerprint,
)
from plm_assistant.modules.ai.application.input_resolution import AIResolvedInputVersionRef
from plm_assistant.modules.ai.application.task_execution_grant import AITaskExecutionGrantError
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_grant_repository import (
    SqlAlchemyAITaskExecutionGrantRepository,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import AITaskExecutionClaims
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def connect(name: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


class Guard:
    def require_valid(self, **_kwargs):
        return object()


def seed_task(db, *, actor, project, authorization, authorization_fingerprint_value,
              approved_at, valid_until, source_fingerprint, object_id, version_id,
              prompt, snapshot_model, snapshot_payload, label):
    task_id, job_id, trace_id, snapshot_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    )
    payload = {
        "ai_task_id": str(task_id),
        "egress_authorization_ref": str(authorization),
        "input_fingerprint": source_fingerprint.hex(),
    }
    params = Jsonb({"language": "zh-CN"})
    db.execute(
        "INSERT INTO plm.job_jobs(job_id,owner_module,job_type,scope,project_id,"
        "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "(%s,'ai','AI_TASK_EXECUTE','PROJECT',%s,%s,%s,%s,%s,2)",
        (job_id, project, actor, str(trace_id), Jsonb(payload), str(task_id)),
    )
    db.execute(
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
        "prompt_template_ref,prompt_version_no,prompt_policy_version,task_parameters,"
        "task_parameters_fingerprint,job_ref,trace_id) VALUES "
        "(%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap-analysis.v1',"
        "'gap-output.v1','project-documents.v1',%s,1,7,%s,"
        "sha256(convert_to(%s::jsonb::text,'UTF8')),%s,%s)",
        (task_id, project, actor, source_fingerprint, prompt, params, params,
         job_id, trace_id),
    )
    db.execute(
        "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
        "owner_module,object_type,object_id,version_id) VALUES "
        "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
        (task_id, project, object_id, version_id),
    )
    db.execute(
        "INSERT INTO plm.ai_egress_authorization_snapshots("
        "egress_authorization_snapshot_id,ai_task_id,scope,project_id,"
        "authorization_ref,purpose_ref,ai_provider_id,provider_config_version_id,"
        "ai_model_id,data_region,allowed_data_categories,authorization_fingerprint,"
        "preview_payload_fingerprint,source_refs_fingerprint,approved_by,approved_role,"
        "approved_at,valid_until,max_payload_bytes,max_input_tokens,max_retry_attempts,"
        "authorization_state_at_capture) SELECT "
        "%s,%s,'PROJECT',%s,%s,'gap.analysis.v1',ai_provider_id,"
        "provider_config_version_id,%s,'cn-beijing',%s,%s,%s,%s,%s,"
        "'PROJECT_MANAGER',%s,%s,32768,2048,2,'AUTHORIZED' "
        "FROM plm.ai_egress_authorizations WHERE authorization_id=%s",
        (snapshot_id, task_id, project, authorization, snapshot_model,
         Jsonb(["DOCUMENT_TEXT"]), authorization_fingerprint_value,
         snapshot_payload, source_fingerprint, actor, approved_at, valid_until,
         authorization),
    )
    db.execute(
        "INSERT INTO plm.job_outbox_events(event_type,owner_module,scope,project_id,"
        "aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id) VALUES "
        "('AI_TASK_QUEUED','ai','PROJECT',%s,%s,0,%s,%s,%s)",
        (project, task_id, Jsonb({"ai_task_id": str(task_id), "job_id": str(job_id)}),
         str(task_id), str(trace_id)),
    )
    return task_id, job_id, label


def revoke(db, *, actor, project, authorization):
    with db.transaction():
        trace = uuid.uuid4()
        audit = db.execute(
            "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
            "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
            "target_object_id) VALUES (%s,'PROJECT',%s,'USER',%s,"
            "'AI_EGRESS_REVOKED','SUCCESS','ai','AI-04',%s) RETURNING audit_event_id",
            (trace, project, actor, authorization),
        ).fetchone()[0]
        revocation, revoked_at = db.execute(
            "INSERT INTO plm.ai_egress_authorization_revocations(authorization_id,"
            "revoked_by,revoked_role,reason_code,reason_summary,audit_event_id,trace_id) "
            "VALUES (%s,%s,'OriginalApprover','USER_REQUEST','Grant revocation proof',%s,%s) "
            "RETURNING revocation_id,revoked_at",
            (authorization, actor, audit, trace),
        ).fetchone()
        db.execute(
            "UPDATE plm.ai_egress_authorizations SET authorization_state='REVOKED',"
            "lock_version=1 WHERE authorization_id=%s", (authorization,),
        )
        db.execute(
            "INSERT INTO plm.ai_egress_revoke_results(result_id,authorization_id,"
            "revocation_id,actor_id,revoked_role,audit_event_id,trace_id,result_state,"
            "lock_version,revoked_at) VALUES (%s,%s,%s,%s,'OriginalApprover',%s,%s,"
            "'REVOKED',1,%s)",
            (uuid.uuid4(), authorization, revocation, actor, audit, trace, revoked_at),
        )


def main() -> None:
    name = "ai04a06p03a03_" + uuid.uuid4().hex[:10]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        with connect(name) as db:
            actor = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('Grant Worker','grant worker') RETURNING user_id",
            ).fetchone()[0]
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('GRANTPG1','grantpg1','Grant PG',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
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
                    "(%s,%s,1,'OPENAI_COMPATIBLE','Grant Provider','endpoint.grant.v1',%s,"
                    "'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                    (config, provider, secret, actor),
                )
            model = db.execute(
                "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                "model_revision,model_state,created_by) VALUES "
                "(%s,'deepseek-chat','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                (provider, actor),
            ).fetchone()[0]
            other_model = db.execute(
                "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                "model_revision,model_state,created_by) VALUES "
                "(%s,'deepseek-chat-alt','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                (provider, actor),
            ).fetchone()[0]
            prompt = uuid.uuid4()
            stale_prompt = uuid.uuid4()
            with db.transaction():
                for template in (prompt, stale_prompt):
                    db.execute(
                        "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
                        "template_state,active_version_no,created_by) "
                        "VALUES (%s,'GAP_ANALYSIS','ACTIVE',%s,%s)",
                        (template, 1, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                        "system_template,user_template,system_template_hash,user_template_hash,"
                        "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,"
                        "created_by) VALUES (%s,1,'System','User {{input}}',%s,%s,"
                        "'gap-output.v1',3,'project-documents.v1','deepseek-chat.v1',%s)",
                        (template, "a" * 64, "b" * 64, actor),
                    )
            object_id, version_id = uuid.uuid4(), uuid.uuid4()
            resolved = (AIResolvedInputVersionRef(
                "DOC-02", "document", "DOCUMENT_VERSION", object_id,
                version_id, "PROJECT", project,
            ),)
            source_fingerprint = input_refs_fingerprint(resolved)
            preview = db.execute(
                "INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,"
                "ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
                "allowed_data_categories,minimal_payload_policy_ref,estimated_record_count,"
                "max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,"
                "source_refs_fingerprint,risk_codes,created_by,trace_id,expires_at) VALUES "
                "('PROJECT',%s,'gap.analysis.v1','AI_TASK',%s,%s,%s,'cn-beijing',%s,"
                "'minimum.document.text.v1',10,65536,4096,2,%s,%s,%s,%s,%s,"
                "statement_timestamp()+interval '30 minutes') RETURNING egress_preview_id",
                (project, provider, config, model, Jsonb(["DOCUMENT_TEXT"]),
                 b"p" * 32, source_fingerprint, Jsonb(["EXTERNAL_PROVIDER"]),
                 actor, uuid.uuid4()),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,ref_ordinal,"
                "resource_type,owner_module,object_type,object_id,version_id,scope,project_id) "
                "VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',%s,%s,'PROJECT',%s)",
                (preview, object_id, version_id, project),
            )
            authorization = uuid.uuid4()
            with db.transaction():
                approved_at, valid_until = db.execute(
                    "INSERT INTO plm.ai_egress_authorizations(authorization_id,egress_preview_id,"
                    "scope,project_id,purpose_ref,operation_type,ai_provider_id,"
                    "provider_config_version_id,ai_model_id,data_region,allowed_data_categories,"
                    "minimal_payload_policy_ref,max_record_count,max_payload_bytes,max_input_tokens,"
                    "max_retry_attempts,payload_fingerprint,source_refs_fingerprint,approved_by,"
                    "approved_role,valid_until) VALUES (%s,%s,'PROJECT',%s,'gap.analysis.v1',"
                    "'AI_TASK',%s,%s,%s,'cn-beijing',%s,'minimum.document.text.v1',8,32768,"
                    "2048,2,%s,%s,%s,'ProjectManager',statement_timestamp()+interval '20 minutes') "
                    "RETURNING approved_at,valid_until",
                    (authorization, preview, project, provider, config, model,
                     Jsonb(["DOCUMENT_TEXT"]), b"p" * 32, source_fingerprint, actor),
                ).fetchone()
                authorize_trace = uuid.uuid4()
                authorize_audit = db.execute(
                    "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                    "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
                    "target_object_id) VALUES (%s,'PROJECT',%s,'USER',%s,"
                    "'AI_EGRESS_AUTHORIZED','SUCCESS','ai','AI-04',%s) "
                    "RETURNING audit_event_id",
                    (authorize_trace, project, actor, authorization),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.ai_egress_authorize_results(result_id,authorization_id,"
                    "egress_preview_id,actor_id,approved_role,audit_event_id,trace_id,"
                    "result_state,lock_version,approved_at,valid_until) VALUES "
                    "(%s,%s,%s,%s,'ProjectManager',%s,%s,'AUTHORIZED',0,%s,%s)",
                    (uuid.uuid4(), authorization, preview, actor, authorize_audit,
                     authorize_trace, approved_at, valid_until),
                )
            view = EgressAuthorizationView(
                authorization, preview, project, "gap.analysis.v1", "AI_TASK",
                provider, config, model, "cn-beijing", ("DOCUMENT_TEXT",),
                "minimum.document.text.v1", 8, 32768, 2048, 2,
                b"p" * 32, source_fingerprint, actor, "ProjectManager",
                approved_at, valid_until, "AUTHORIZED", 0,
            )
            auth_fingerprint = authorization_fingerprint(view)
            cases = {}
            for args in (
                (prompt, model, b"p" * 32, "VALID"),
                (stale_prompt, model, b"p" * 32, "STALE_PROMPT"),
                (prompt, other_model, b"p" * 32, "MODEL_DRIFT"),
                (prompt, model, b"x" * 32, "PAYLOAD_DRIFT"),
            ):
                seeded = seed_task(
                    db, actor=actor, project=project, authorization=authorization,
                    authorization_fingerprint_value=auth_fingerprint,
                    approved_at=approved_at, valid_until=valid_until,
                    source_fingerprint=source_fingerprint, object_id=object_id,
                    version_id=version_id, prompt=args[0], snapshot_model=args[1],
                    snapshot_payload=args[2], label=args[3],
                )
                cases[seeded[1]] = seeded
            # The Task captured version 1 while it was current; version 2 becomes
            # current afterwards, proving execution-time Prompt drift rejection.
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                    "system_template,user_template,system_template_hash,user_template_hash,"
                    "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,"
                    "created_by) VALUES (%s,2,'System v2','User v2 {{input}}',%s,%s,"
                    "'gap-output.v1',3,'project-documents.v1','deepseek-chat.v1',%s)",
                    (stale_prompt, "c" * 64, "d" * 64, actor),
                )
                db.execute(
                    "UPDATE plm.ai_prompt_templates SET active_version_no=2,lock_version=1 "
                    "WHERE prompt_template_id=%s", (stale_prompt,),
                )

        runtime = create_database_runtime(url)
        leases = JobLeaseService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyJobLeaseRepository(),
        )
        issuer = AITaskExecutionGrantIssuer(
            unit_of_work=runtime.unit_of_work,
            claims=AITaskExecutionClaims(
                repository=SqlAlchemyAITaskExecutionClaimRepository(),
            ),
            repository=SqlAlchemyAITaskExecutionGrantRepository(),
            egress_owner=EgressAuthorizationOwner(
                repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
                purposes=AITaskEgressPurposeRegistry({
                    "GAP_ANALYSIS": frozenset({"gap.analysis.v1"}),
                }),
            ),
            license_guard=Guard(),
        )
        worker = "ai-grant-worker-01"
        seen = set()
        for _ in range(4):
            current = leases.claim_next(worker_ref=worker, lease_seconds=120)
            assert current is not None
            task_id, _, label = cases[current.job_id]
            seen.add(label)
            try:
                grant = issuer.issue(
                    job_id=current.job_id, fencing_token=current.fencing_token,
                    worker_ref=worker, now=datetime.now(timezone.utc),
                )
            except AITaskExecutionGrantError:
                assert label != "VALID", label
            else:
                assert label == "VALID", label
                assert grant.ai_task_id == task_id
                assert grant.input_refs[0].resource_type == "DOC-02"
                assert grant.prompt_version_no == 1 and grant.schema_version == 3
                assert grant.provider_model_key == "deepseek-chat"
                assert grant.minimal_payload_policy_ref == "minimum.document.text.v1"
                assert (grant.max_record_count, grant.max_payload_bytes,
                        grant.max_input_tokens, grant.max_retry_attempts) == (
                            8, 32768, 2048, 2,
                        )
            leases.retry_or_fail(
                job_id=current.job_id, fencing_token=current.fencing_token,
                worker_ref=worker, error_code="SYNTHETIC_DONE", retryable=False,
            )
        assert seen == {"VALID", "STALE_PROMPT", "MODEL_DRIFT", "PAYLOAD_DRIFT"}

        with connect(name) as db:
            revoked_case = seed_task(
                db, actor=actor, project=project, authorization=authorization,
                authorization_fingerprint_value=auth_fingerprint,
                approved_at=approved_at, valid_until=valid_until,
                source_fingerprint=source_fingerprint, object_id=object_id,
                version_id=version_id, prompt=prompt, snapshot_model=model,
                snapshot_payload=b"p" * 32, label="REVOKED",
            )
            revoke(db, actor=actor, project=project, authorization=authorization)
        current = leases.claim_next(worker_ref=worker, lease_seconds=120)
        assert current is not None and current.job_id == revoked_case[1]
        try:
            issuer.issue(
                job_id=current.job_id, fencing_token=current.fencing_token,
                worker_ref=worker, now=datetime.now(timezone.utc),
            )
        except AITaskExecutionGrantError:
            pass
        else:
            raise AssertionError("revoked authorization produced a grant")
        with connect(name) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations"
            ).fetchone()[0] == 0
        print(
            "AI_04_A06_P03_P01_A03_EXECUTION_GRANT_PG_PASS: Windows 11, "
            "PostgreSQL 18, current Jobs claim plus exact Task/Input/Prompt/Model/Egress "
            "metadata issued one non-content grant; stale Prompt, model/payload drift and "
            "revoked authorization rejected; no Invocation or Provider call"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
