"""Windows 11/PostgreSQL 18 proof for exact Prompt/Task content projection."""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import input_refs_fingerprint
from plm_assistant.modules.ai.application.egress_authorization import EgressAuthorizationView
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry,
    EgressAuthorizationOwner,
    authorization_fingerprint,
)
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    AIExecutionContentSourceIdentity,
    AIExecutionContextIdentity,
    AIExecutionPromptIdentity,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptContentError,
    AIExecutionPromptTaskContentOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.input_resolution import AIResolvedInputVersionRef
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_content_repository import (
    SqlAlchemyAIExecutionPromptTaskContentRepository,
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


BASE_PATH = pathlib.Path(__file__).parents[1] / (
    "ai-04-a06-p03-p01-a03-execution-grant-pg/verify.py"
)
SPEC = importlib.util.spec_from_file_location("ai04a06_grant_pg", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def main() -> None:
    name = "ai04a06p03p02a02_" + uuid.uuid4().hex[:8]
    url = URL.create(
        "postgresql+psycopg", username=BASE.USER, host=BASE.HOST,
        port=BASE.PORT, database=name,
    )
    with BASE.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        system = "Use only this authorized context:\n{context}"
        user = "Parameters: {parameters}\nInput: {input}"
        system_hash = hashlib.sha256(system.encode("utf-8")).hexdigest()
        user_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()
        with BASE.connect(name) as db:
            actor = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('Prompt Worker','prompt worker') RETURNING user_id",
            ).fetchone()[0]
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('PROMPTPG1','promptpg1','Prompt PG',%s) RETURNING project_id",
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
                    "(%s,%s,1,'OPENAI_COMPATIBLE','Prompt Provider','endpoint.prompt.v1',%s,"
                    "'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
                    (config, provider, secret, actor),
                )
            model = db.execute(
                "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                "model_revision,model_state,created_by) VALUES "
                "(%s,'deepseek-chat','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
                (provider, actor),
            ).fetchone()[0]
            prompt = uuid.uuid4()
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
                    "template_state,active_version_no,created_by) "
                    "VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)",
                    (prompt, actor),
                )
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                    "system_template,user_template,system_template_hash,user_template_hash,"
                    "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,"
                    "created_by) VALUES (%s,1,%s,%s,%s,%s,'gap-output.v1',3,"
                    "'project-documents.v1','deepseek-chat.v1',%s)",
                    (prompt, system, user, system_hash, user_hash, actor),
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
                    "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,actor_type,"
                    "actor_id,action,outcome,target_owner_module,target_object_type,target_object_id) "
                    "VALUES (%s,'PROJECT',%s,'USER',%s,'AI_EGRESS_AUTHORIZED','SUCCESS',"
                    "'ai','AI-04',%s) RETURNING audit_event_id",
                    (authorize_trace, project, actor, authorization),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.ai_egress_authorize_results(result_id,authorization_id,"
                    "egress_preview_id,actor_id,approved_role,audit_event_id,trace_id,result_state,"
                    "lock_version,approved_at,valid_until) VALUES "
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
            task_id, job_id, _ = BASE.seed_task(
                db, actor=actor, project=project, authorization=authorization,
                authorization_fingerprint_value=authorization_fingerprint(view),
                approved_at=approved_at, valid_until=valid_until,
                source_fingerprint=source_fingerprint, object_id=object_id,
                version_id=version_id, prompt=prompt, snapshot_model=model,
                snapshot_payload=b"p" * 32, label="VALID",
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
            license_guard=BASE.Guard(),
        )
        claimed = leases.claim_next(worker_ref="prompt-worker-01", lease_seconds=120)
        assert claimed is not None and claimed.job_id == job_id
        grant = issuer.issue(
            job_id=job_id, fencing_token=claimed.fencing_token,
            worker_ref="prompt-worker-01", now=datetime.now(timezone.utc),
        )
        owner = AIExecutionPromptTaskContentOwner(
            SqlAlchemyAIExecutionPromptTaskContentRepository(),
        )
        with runtime.unit_of_work() as tx:
            content = owner.load_exact(tx, grant=grant)
        assert content.ai_task_id == task_id
        assert content.canonical_parameters_json == '{"language":"zh-CN"}'
        assert system not in repr(content) and "zh-CN" not in repr(content)

        source = AIExecutionContentSourceIdentity(
            1, "DOC-02", "document", "DOCUMENT_VERSION", object_id,
            version_id, project, "DOCUMENT_PARSED_TEXT", uuid.uuid4(),
            uuid.uuid4(), "document-parser.standard", "1.0.0",
            "document.parse-result.v1", "document.parse.fixed.v1",
            b"d" * 32, b"e" * 32, b"f" * 32, 1024, 1,
        )
        prompt_identity = AIExecutionPromptIdentity(
            grant.prompt_policy_ref, grant.prompt_policy_version,
            grant.prompt_template_id, grant.prompt_version_no,
            grant.system_template_hash, grant.user_template_hash,
            grant.provider_policy_ref, grant.output_schema_ref,
            grant.schema_version, "strict-placeholders.v1", 1,
        )
        context = AIExecutionContextIdentity(
            grant.context_policy_ref, "RAG_CONTEXT", uuid.uuid4(), uuid.uuid4(),
            b"g" * 32, 1, 128,
        )
        plan = AIExecutionContentPlan(
            uuid.uuid4(), 1, project, grant.purpose_ref, grant.task_type,
            grant.source_refs_fingerprint, (source,), prompt_identity,
            grant.task_parameters_fingerprint, context, grant.ai_provider_id,
            grant.provider_config_version_id, grant.ai_model_id,
            grant.provider_model_key, grant.model_revision, grant.data_region,
            tuple(sorted(grant.allowed_data_categories)),
            grant.minimal_payload_policy_ref, "provider-neutral-json.v1", 1,
            "deepseek-chat.tokens.v1", 1,
        )
        rendered = StrictAIExecutionPromptRenderer().render(
            plan, content, input_text="合成输入 {context}", context_text="合成证据",
        )
        assert b"{context}" in rendered.user_utf8
        assert len(rendered.fingerprint) == 32

        with runtime.unit_of_work() as tx:
            try:
                owner.load_exact(
                    tx, grant=replace(grant, task_parameters_fingerprint=b"x" * 32),
                )
            except AIExecutionPromptContentError:
                pass
            else:
                raise AssertionError("parameter fingerprint drift was accepted")

        with BASE.connect(name) as db:
            replacement_system, replacement_user = "System v2", "{input} {context} {parameters}"
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                    "system_template,user_template,system_template_hash,user_template_hash,"
                    "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,created_by) "
                    "VALUES (%s,2,%s,%s,%s,%s,'gap-output.v1',3,'project-documents.v1',"
                    "'deepseek-chat.v1',%s)",
                    (prompt, replacement_system, replacement_user,
                     hashlib.sha256(replacement_system.encode()).hexdigest(),
                     hashlib.sha256(replacement_user.encode()).hexdigest(), actor),
                )
                db.execute(
                    "UPDATE plm.ai_prompt_templates SET active_version_no=2,lock_version=1 "
                    "WHERE prompt_template_id=%s", (prompt,),
                )
        with runtime.unit_of_work() as tx:
            try:
                owner.load_exact(tx, grant=grant)
            except AIExecutionPromptContentError:
                pass
            else:
                raise AssertionError("active Prompt drift was accepted")

        with BASE.connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.ai_invocations").fetchone()[0] == 0
        print(
            "AI_04_A06_P03_P02_A02_PROMPT_CONTENT_PG_PASS: Windows 11, "
            "PostgreSQL 18, exact active Prompt and scalar Task parameters projected "
            "without repr leakage; strict UTF-8 rendering preserved inserted braces; "
            "parameter and active Prompt drift rejected; no Invocation or Provider call"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with BASE.connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
