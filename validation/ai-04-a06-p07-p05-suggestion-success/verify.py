"""Windows 11/PostgreSQL 18 proof for atomic AI suggestion success publication."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.complete_provider_success import (
    AITaskProviderSuccessService,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.provider_response_parser import (
    AIProviderSuggestionParser,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.publish_suggestion_success import (
    AITaskSuggestionPublicationError,
    AITaskSuggestionSuccessPublisher,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
)
from plm_assistant.modules.ai.infrastructure.suggestion_success_repository import (
    SqlAlchemyAITaskSuggestionSuccessRepository,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.secret_store_reader import (
    SqlAlchemyEncryptedSecretStore,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidSuggestionAdapter:
    def __init__(self, expected_key: bytes) -> None:
        self.expected_key = expected_key
        self.calls = 0

    def send(self, **values) -> AIProviderResponse:
        assert values["key"].tobytes() == self.expected_key
        self.calls += 1
        content = json.dumps({
            "schema_ref": "gap-output.v1",
            "schema_version": 1,
            "items": [{
                "category": "PENDING_CONFIRMATION",
                "title": "接口边界",
                "summary": "当前授权资料未固定回写范围。",
                "rationale": "输入资料只证明接口需求存在。",
                "recommendation": "确认字段、触发条件与失败补偿。",
                "source_ordinals": [1],
            }],
        }, ensure_ascii=False, separators=(",", ":"))
        body = json.dumps({
            "choices": [{"message": {"content": content},
                         "finish_reason": "stop"}],
        }, ensure_ascii=False, separators=(",", ":")).encode()
        return AIProviderResponse(bytearray(body), AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body), 100, 50, 9, "STOP",
        ))


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


def validate(context: dict[str, object]) -> None:
    helper = load_helper(
        "ai-04-a06-p07-p03-provider-send-fence", "p07p05_send_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p07p05_schema_helper",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    initial = context["authorized_send"]
    runtime = context["runtime"]
    username = "synthetic-ai-result-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
    actor = helper.load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p07p05_orchestration_helper",
    ).FixedSystemActor(system_id)
    audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=actor,
    )
    orchestration = helper.load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p07p05_orchestration_classes",
    )
    decryptor = orchestration.SyntheticDecryptor(
        initial.route.secret_version_id,
    )
    secrets = SecretResolver(
        SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), decryptor, audit,
    )
    pre_send = orchestration.CountingPreSend(context["pre_send_service"])
    fence = AITaskProviderSendFenceService(
        unit_of_work=runtime.unit_of_work,
        claims=AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        ),
        repository=SqlAlchemyAITaskProviderSendFenceRepository(),
    )
    adapter = ValidSuggestionAdapter(b"synthetic-task-key-not-for-network")
    send = AITaskProviderSendService(
        pre_send=pre_send, secrets=secrets, adapter=adapter,
        access_audit_scope=audit, send_fence=fence,
        clock=lambda: datetime.now(timezone.utc),
    )
    response = send.send_once(
        prepared=prepared, begun=begun, job_id=current.job_id,
        fencing_token=current.fencing_token,
        worker_ref=context["worker_ref"],
    )
    parser = AIProviderSuggestionParser(
        schemas=default_ai_output_schema_registry(),
    )
    parsed = parser.parse(
        prepared=prepared, begun=begun, response=response,
    )
    plans = AIExecutionContentPlanOwner(
        SqlAlchemyAIExecutionContentPlanRepository(),
    )
    store = SqlAlchemyAITaskSuggestionSuccessRepository()
    failing = AITaskSuggestionSuccessPublisher(
        unit_of_work=runtime.unit_of_work, plans=plans, store=store,
        jobs=SqlAlchemyJobLeaseRepository(), audit=FailingAudit(),
        system_actor=actor,
    )
    try:
        failing.publish(
            parsed=parsed, prepared=prepared, begun=begun,
            worker_ref=context["worker_ref"],
        )
    except AITaskSuggestionPublicationError:
        pass
    else:
        raise AssertionError("audit failure committed AI suggestion")
    with schema.connect(context["database"]) as db:
        rolled_back = db.execute(
            "SELECT t.task_state,t.suggestion_state,i.invocation_state,j.state,"
            "(SELECT count(*) FROM plm.ai_suggestion_payloads) "
            "FROM plm.ai_tasks t JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref "
            "JOIN plm.job_jobs j ON j.job_id=t.job_ref "
            "WHERE t.ai_task_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
    assert rolled_back == ("RUNNING", "NONE", "RUNNING", "RUNNING", 0)

    publisher = AITaskSuggestionSuccessPublisher(
        unit_of_work=runtime.unit_of_work, plans=plans, store=store,
        jobs=SqlAlchemyJobLeaseRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()), system_actor=actor,
    )
    success = AITaskProviderSuccessService(parser=parser, publisher=publisher)
    result = success.complete(
        prepared=prepared, begun=begun, response=response,
        worker_ref=context["worker_ref"],
    )
    assert adapter.calls == 1
    assert all(not any(value) for value in decryptor.buffers)
    try:
        response.view()
    except Exception:
        pass
    else:
        raise AssertionError("published Provider response remained readable")

    with schema.connect(context["database"]) as db:
        terminal = db.execute(
            "SELECT t.task_state,t.suggestion_state,t.completed_at,i.invocation_state,"
            "i.schema_validation_state,i.suggestion_payload_ref,i.completed_at,j.state,"
            "j.completed_at,a.completed_at,l.state,p.fact_status,e.ref_ordinal,"
            "e.owner_module,e.object_type,e.content_fingerprint "
            "FROM plm.ai_tasks t JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref "
            "JOIN plm.job_jobs j ON j.job_id=t.job_ref "
            "JOIN plm.job_attempts a ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.job_leases l ON l.job_id=j.job_id AND l.fencing_token=j.fencing_token "
            "JOIN plm.ai_suggestion_payloads p ON p.suggestion_payload_id=i.suggestion_payload_ref "
            "JOIN plm.ai_suggestion_evidence_refs e "
            "ON e.suggestion_payload_id=p.suggestion_payload_id "
            "WHERE t.ai_task_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
        event = db.execute(
            "SELECT outcome,before_state,after_state,target_object_id,target_version_id "
            "FROM plm.aud_events WHERE action='AI_TASK_SUGGESTION_AVAILABLE' "
            "AND trace_id=%s", (prepared.grant.trace_id,),
        ).fetchone()
        source_fingerprint = db.execute(
            "SELECT content_fingerprint FROM plm.ai_execution_content_sources "
            "WHERE content_plan_id=%s AND source_ordinal=1",
            (prepared.grant.content_plan_id,),
        ).fetchone()[0]
    assert terminal[0:2] == ("SUCCEEDED", "AVAILABLE")
    assert terminal[2] is not None
    assert terminal[3:6] == ("SUCCEEDED", "VALID", result.suggestion_payload_id)
    assert terminal[6] is not None
    assert terminal[7] == "SUCCEEDED" and terminal[8] == terminal[9]
    assert terminal[10:15] == (
        "RELEASED", "NOT_FORMAL_FACT", 1, "document", "DOCUMENT_VERSION",
    )
    assert terminal[15] == source_fingerprint
    assert event == (
        "SUCCESS", "RUNNING", "AVAILABLE", prepared.grant.ai_task_id,
        result.suggestion_payload_id,
    )
    print(
        "AI_04_A06_P07_P05_SUGGESTION_SUCCESS_PASS: Win11/PostgreSQL18.6 "
        "resolved authorized source ordinal to immutable Content Plan evidence, rolled "
        "back Job/Suggestion/Invocation/Task when Audit failed, then atomically committed "
        "NOT_FORMAL_FACT Suggestion, Evidence, SUCCEEDED/VALID Invocation, AVAILABLE Task, "
        "released Job generation and Project Audit; one synthetic Adapter call only, "
        "response/key zeroized, zero real Provider network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p07p05_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
