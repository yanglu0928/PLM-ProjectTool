"""Windows 11/PostgreSQL 18 proof for one complete business AI Worker cycle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskOneShotWorker,
)
from plm_assistant.modules.ai.application.complete_provider_failure import (
    AITaskProviderFailureService,
)
from plm_assistant.modules.ai.application.complete_provider_success import (
    AITaskProviderSuccessService,
)
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptTaskContentOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.provider_execution_pre_send import (
    AIProviderPreSendService,
)
from plm_assistant.modules.ai.application.provider_response_parser import (
    AIProviderSuggestionParser,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    AITaskPreBeginFailurePublisher,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    AITaskSuggestionSuccessPublisher,
)
from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePublisher,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.application.task_execution_grant_service import (
    AITaskExecutionGrantIssuer,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginService,
)
from plm_assistant.modules.ai.application.task_invocation_prepare import (
    AITaskInvocationPrepareService,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_content_repository import (
    SqlAlchemyAIExecutionPromptTaskContentRepository,
)
from plm_assistant.modules.ai.infrastructure.pre_begin_failure_repository import (
    SqlAlchemyAITaskPreBeginFailureRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_execution_route_repository import (
    SqlAlchemyAIProviderExecutionRouteRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
)
from plm_assistant.modules.ai.infrastructure.suggestion_success_repository import (
    SqlAlchemyAITaskSuggestionSuccessRepository,
)
from plm_assistant.modules.ai.infrastructure.task_execution_grant_repository import (
    SqlAlchemyAITaskExecutionGrantRepository,
)
from plm_assistant.modules.ai.infrastructure.task_failure_repository import (
    SqlAlchemyAITaskFailureRepository,
)
from plm_assistant.modules.ai.infrastructure.task_invocation_begin_repository import (
    SqlAlchemyAITaskInvocationBeginRepository,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentService,
)
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import (
    SqlAlchemyAIProviderSecretProof,
)
from plm_assistant.modules.platform.infrastructure.secret_store_reader import (
    SqlAlchemyEncryptedSecretStore,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidSuggestionAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, **values) -> AIProviderResponse:
        assert values["key"].tobytes() == b"synthetic-task-key-not-for-network"
        self.calls += 1
        content = json.dumps({
            "schema_ref": "gap-output.v1",
            "schema_version": 1,
            "items": [{
                "category": "PENDING_CONFIRMATION",
                "title": "合成接口边界",
                "summary": "只验证一次性Worker编排。",
                "rationale": "输入仅为合成资料。",
                "recommendation": "后续仍须人工确认。",
                "source_ordinals": [1],
            }],
        }, ensure_ascii=False, separators=(",", ":"))
        body = json.dumps({
            "choices": [{"message": {"content": content},
                         "finish_reason": "stop"}],
        }, ensure_ascii=False, separators=(",", ":")).encode()
        return AIProviderResponse(bytearray(body), AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body), 120, 40, 8, "STOP",
        ))


def validate(context: dict[str, object]) -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p09p03_schema",
    )
    orchestration = load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p09p03_orchestration",
    )
    runtime = context["runtime"]
    with schema.connect(context["database"]) as db:
        username = "business-ai-worker-" + uuid.uuid4().hex[:12]
        system_actor_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
        secret_ref, created_by = db.execute(
            "SELECT c.secret_ref,c.created_by FROM plm.ai_provider_config_versions c "
            "WHERE c.config_version_no=1",
        ).fetchone()
        secret_version = uuid.uuid4()
        with db.transaction():
            db.execute(
                "INSERT INTO plm.plt_secret_versions(secret_version_id,secret_record_id,"
                "version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by,"
                "activated_at) VALUES (%s,%s,1,%s,'{}'::jsonb,'synthetic-only',%s,"
                "statement_timestamp())",
                (secret_version, secret_ref, b"synthetic-ciphertext", created_by),
            )
            db.execute(
                "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',"
                "current_version_ref=%s,lock_version=lock_version+1,"
                "updated_at=statement_timestamp() WHERE secret_record_id=%s",
                (secret_version, secret_ref),
            )

    actor = orchestration.FixedSystemActor(system_actor_id)
    audit = AuditService(SqlAlchemyAuditRepository())
    lease_repository = SqlAlchemyJobLeaseRepository()
    claims = AITaskExecutionClaims(
        repository=SqlAlchemyAITaskExecutionClaimRepository(),
    )
    egress = EgressAuthorizationOwner(
        repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
        purposes=context["purposes"],
    )
    grants = AITaskExecutionGrantIssuer(
        unit_of_work=runtime.unit_of_work, claims=claims,
        repository=SqlAlchemyAITaskExecutionGrantRepository(),
        egress_owner=egress, license_guard=context["guard"],
    )
    plans = AIExecutionContentPlanOwner(
        SqlAlchemyAIExecutionContentPlanRepository(),
    )
    projects = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    document_owner = AIDocumentContentOwner(DocumentAIContentService(
        repository=SqlAlchemyDocumentAIContentRepository(),
        storage=LocalParseResultStorage(context["result_root"]),
        projects=projects, license_guard=context["guard"],
    ))
    preparer = AITaskInvocationPrepareService(
        unit_of_work=runtime.unit_of_work, grants=grants, plans=plans,
        prompts=AIExecutionPromptTaskContentOwner(
            SqlAlchemyAIExecutionPromptTaskContentRepository(),
        ),
        source_owners={"DOC-02": document_owner},
        envelopes=AIExecutionEnvelopeBuilder(
            renderer=StrictAIExecutionPromptRenderer(),
            context_policies=AIExecutionContextPolicyRegistry(
                frozenset({"no-retrieval.v1"}),
            ),
            token_estimators=AIExecutionTokenEstimatorRegistry((
                Utf8ByteUpperBoundTokenEstimator(),
            )),
        ),
    )
    beginner = AITaskInvocationBeginService(
        unit_of_work=runtime.unit_of_work, grants=grants,
        repository=SqlAlchemyAITaskInvocationBeginRepository(),
    )
    pre_send = AIProviderPreSendService(
        unit_of_work=runtime.unit_of_work, claims=claims,
        repository=SqlAlchemyAIProviderExecutionRouteRepository(),
        egress_owner=egress, secret_proof=SqlAlchemyAIProviderSecretProof(),
        policies=AIProviderExecutionPolicyRegistry((
            AIProviderExecutionPolicy(
                "endpoint.content-plan.v1", ProviderKind.OPENAI_COMPATIBLE,
                "https://api.example.test/v1/chat/completions", "cn-beijing",
                "EXTERNAL_APPROVAL_REQUIRED", frozenset({"content-plan-chat"}),
                1_000_000, 3, 10, 20,
            ),
        )),
        license_guard=context["guard"],
    )
    secret_audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work, audit=audit, system_actor=actor,
    )
    decryptor = orchestration.SyntheticDecryptor(secret_version)
    adapter = ValidSuggestionAdapter()
    sender = AITaskProviderSendService(
        pre_send=pre_send,
        secrets=SecretResolver(
            SqlAlchemyEncryptedSecretStore(runtime.unit_of_work),
            decryptor, secret_audit,
        ),
        adapter=adapter, access_audit_scope=secret_audit,
        send_fence=AITaskProviderSendFenceService(
            unit_of_work=runtime.unit_of_work, claims=claims,
            repository=SqlAlchemyAITaskProviderSendFenceRepository(),
        ),
        clock=lambda: datetime.now(timezone.utc),
    )
    failure_publisher = AITaskFailurePublisher(
        unit_of_work=runtime.unit_of_work,
        store=SqlAlchemyAITaskFailureRepository(), jobs=lease_repository,
        audit=audit, system_actor=actor,
    )
    task_failure = AITaskProviderFailureService(publisher=failure_publisher)
    success = AITaskProviderSuccessService(
        parser=AIProviderSuggestionParser(
            schemas=default_ai_output_schema_registry(),
        ),
        publisher=AITaskSuggestionSuccessPublisher(
            unit_of_work=runtime.unit_of_work, plans=plans,
            store=SqlAlchemyAITaskSuggestionSuccessRepository(),
            jobs=lease_repository, audit=audit, system_actor=actor,
        ),
        failures=failure_publisher,
    )
    worker = AIBusinessTaskOneShotWorker(
        leases=JobLeaseService(
            unit_of_work=runtime.unit_of_work, repository=lease_repository,
        ),
        preparer=preparer, beginner=beginner, sender=sender,
        success=success, failure=task_failure,
        pre_begin_failure=AITaskPreBeginFailurePublisher(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyAITaskPreBeginFailureRepository(),
            jobs=lease_repository, audit=audit, system_actor=actor,
        ),
        clock=lambda: datetime.now(timezone.utc),
    )
    result = worker.run_once(worker_ref="business-ai-one-shot-proof")
    assert result.state == "SUCCEEDED" and result.job_id == context["job_id"]
    assert result.result_id is not None and adapter.calls == 1
    assert all(not any(value) for value in decryptor.buffers)
    assert worker.run_once(worker_ref="business-ai-one-shot-proof").state == "IDLE"

    with schema.connect(context["database"]) as db:
        terminal = db.execute(
            "SELECT t.task_state,t.suggestion_state,i.invocation_state,"
            "i.schema_validation_state,i.suggestion_payload_ref,j.state,l.state,"
            "a.error_code,(SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=t.ai_task_id) "
            "FROM plm.ai_tasks t JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref "
            "JOIN plm.job_jobs j ON j.job_id=t.job_ref "
            "JOIN plm.job_leases l ON l.job_id=j.job_id AND l.fencing_token=j.fencing_token "
            "JOIN plm.job_attempts a ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "WHERE t.ai_task_id=%s", (context["ai_task_id"],),
        ).fetchone()
        events = db.execute(
            "SELECT action,outcome FROM plm.aud_events WHERE target_object_id=%s "
            "AND action IN ('AI_TASK_PREPARATION_FAILED','AI_TASK_EXECUTION_FAILED',"
            "'AI_TASK_SUGGESTION_AVAILABLE') ORDER BY action",
            (context["ai_task_id"],),
        ).fetchall()
    assert terminal == (
        "SUCCEEDED", "AVAILABLE", "SUCCEEDED", "VALID", result.result_id,
        "SUCCEEDED", "RELEASED", None, 1,
    )
    assert events == [("AI_TASK_SUGGESTION_AVAILABLE", "SUCCESS")]
    print(
        "AI_04_A06_P09_P03_BUSINESS_ONE_SHOT_PASS: Windows11/PostgreSQL18.6 "
        "one owner-specific claim executed exact Prepare/Begin/double pre-send/Secret/"
        "durable send fence/synthetic Adapter/parse/Suggestion publication order, then "
        "atomically closed Task/Invocation/Job/Lease/Audit; one send, key zeroized, second "
        "cycle IDLE, zero real Provider network or customer data egress"
    )


def main() -> None:
    composition = load_helper(
        "ai-04-a06-p04-p04-a06-windows-composition", "p09p03_composition",
    )
    composition.main(after_validation=validate)


if __name__ == "__main__":
    main()
