"""Windows 11/PostgreSQL 18 proof for atomic post-fence AI failure."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.complete_provider_failure import (
    AITaskProviderFailureService,
)
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
)
from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.publish_task_failure import (
    AITaskFailurePublicationError,
    AITaskFailurePublisher,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendError,
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
)
from plm_assistant.modules.ai.infrastructure.task_failure_repository import (
    SqlAlchemyAITaskFailureRepository,
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


class FailingAdapter:
    def __init__(self, expected_key: bytes) -> None:
        self.expected_key = expected_key
        self.calls = 0

    def send(self, **values):
        assert values["key"].tobytes() == self.expected_key
        self.calls += 1
        raise AIProviderExecutionError("AI_PROVIDER_NETWORK_UNAVAILABLE")


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


def validate(context: dict[str, object]) -> None:
    send_helper = load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p08p02_send_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p08p02_schema_helper",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    initial = context["authorized_send"]
    runtime = context["runtime"]
    username = "synthetic-ai-failure-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
    actor = send_helper.FixedSystemActor(system_id)
    secret_audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=actor,
    )
    decryptor = send_helper.SyntheticDecryptor(initial.route.secret_version_id)
    secrets = SecretResolver(
        SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), decryptor,
        secret_audit,
    )
    adapter = FailingAdapter(b"synthetic-task-key-not-for-network")
    sender = AITaskProviderSendService(
        pre_send=send_helper.CountingPreSend(context["pre_send_service"]),
        secrets=secrets, adapter=adapter, access_audit_scope=secret_audit,
        send_fence=AITaskProviderSendFenceService(
            unit_of_work=runtime.unit_of_work,
            claims=AITaskExecutionClaims(
                repository=SqlAlchemyAITaskExecutionClaimRepository(),
            ),
            repository=SqlAlchemyAITaskProviderSendFenceRepository(),
        ),
        clock=lambda: datetime.now(timezone.utc),
    )
    try:
        sender.send_once(
            prepared=prepared, begun=begun, job_id=current.job_id,
            fencing_token=current.fencing_token,
            worker_ref=context["worker_ref"],
        )
    except AITaskProviderSendError as error:
        assert error.code == "AI_PROVIDER_OUTCOME_UNKNOWN"
        assert error.provider_outcome_unknown
        send_error = error
    else:
        raise AssertionError("synthetic post-fence failure was accepted")
    assert adapter.calls == 1
    assert all(not any(value) for value in decryptor.buffers)

    def publisher(audit):
        return AITaskProviderFailureService(publisher=AITaskFailurePublisher(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyAITaskFailureRepository(),
            jobs=SqlAlchemyJobLeaseRepository(), audit=audit,
            system_actor=actor,
        ))

    try:
        publisher(FailingAudit()).complete(
            prepared=prepared, begun=begun, error=send_error,
            worker_ref=context["worker_ref"],
        )
    except Exception:
        pass
    else:
        raise AssertionError("Audit failure committed AI failure")
    with schema.connect(context["database"]) as db:
        rolled_back = db.execute(
            "SELECT t.task_state,i.invocation_state,j.state,l.state,a.completed_at "
            "FROM plm.ai_tasks t JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref "
            "JOIN plm.job_jobs j ON j.job_id=t.job_ref "
            "JOIN plm.job_leases l ON l.job_id=j.job_id AND l.fencing_token=j.fencing_token "
            "JOIN plm.job_attempts a ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "WHERE t.ai_task_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
    assert rolled_back == ("RUNNING", "RUNNING", "RUNNING", "ACTIVE", None)

    result = publisher(AuditService(SqlAlchemyAuditRepository())).complete(
        prepared=prepared, begun=begun, error=send_error,
        worker_ref=context["worker_ref"],
    )
    assert result.error_code == "AI_PROVIDER_OUTCOME_UNKNOWN"
    assert not result.retryable
    assert adapter.calls == 1
    with schema.connect(context["database"]) as db:
        terminal = db.execute(
            "SELECT t.task_state,t.error_code,t.retryable,t.completed_at,"
            "i.invocation_state,i.schema_validation_state,i.error_code,i.retryable,"
            "i.completed_at,j.state,j.completed_at,l.state,a.error_code,a.completed_at "
            "FROM plm.ai_tasks t JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref "
            "JOIN plm.job_jobs j ON j.job_id=t.job_ref "
            "JOIN plm.job_leases l ON l.job_id=j.job_id AND l.fencing_token=j.fencing_token "
            "JOIN plm.job_attempts a ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "WHERE t.ai_task_id=%s", (prepared.grant.ai_task_id,),
        ).fetchone()
        event = db.execute(
            "SELECT outcome,before_state,after_state,target_version_id "
            "FROM plm.aud_events WHERE action='AI_TASK_EXECUTION_FAILED' "
            "AND trace_id=%s", (prepared.grant.trace_id,),
        ).fetchone()
    assert terminal[0:4] == (
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False, result.completed_at,
    )
    assert terminal[4:9] == (
        "FAILED", "PENDING", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
        result.completed_at,
    )
    assert terminal[9] == "FAILED" and terminal[10] == terminal[13]
    assert terminal[11:13] == ("RELEASED", "AI_PROVIDER_OUTCOME_UNKNOWN")
    assert event == (
        "FAILED", "RUNNING", "FAILED", begun.ai_invocation_id,
    )
    print(
        "AI_04_A06_P08_P02_TASK_FAILURE_PASS: Win11/PostgreSQL18.6 "
        "durably fenced one synthetic Provider call, classified its post-fence "
        "transport failure as non-retryable AI_PROVIDER_OUTCOME_UNKNOWN, rolled "
        "back Job/Invocation/Task on Audit failure, then atomically terminalized "
        "Job/Attempt/Lease/Invocation/Task/Audit without a second Adapter call; "
        "key zeroized and zero real Provider network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p08p02_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
