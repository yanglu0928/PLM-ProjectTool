"""Windows 11/PostgreSQL 18 proof for expired RUNNING AI reconciliation."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.reconcile_expired_task import (
    AITaskReconciliationError,
    ExpiredAITaskReconciler,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.infrastructure.expired_task_reconciliation_repository import (
    SqlAlchemyExpiredAITaskReconciliationRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_send_fence_repository import (
    SqlAlchemyAITaskProviderSendFenceRepository,
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
from plm_assistant.modules.jobs.application.lease import JobLeaseError
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


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


def validate(context: dict[str, object]) -> None:
    send_helper = load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p08p03_send_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p08p03_schema_helper",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    initial = context["authorized_send"]
    runtime = context["runtime"]
    username = "synthetic-ai-reconcile-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
    actor = send_helper.FixedSystemActor(system_id)
    secret_audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()), system_actor=actor,
    )
    decryptor = send_helper.SyntheticDecryptor(initial.route.secret_version_id)
    adapter = send_helper.SyntheticAdapter(
        b"synthetic-task-key-not-for-network",
    )
    response = AITaskProviderSendService(
        pre_send=send_helper.CountingPreSend(context["pre_send_service"]),
        secrets=SecretResolver(
            SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), decryptor,
            secret_audit,
        ),
        adapter=adapter, access_audit_scope=secret_audit,
        send_fence=AITaskProviderSendFenceService(
            unit_of_work=runtime.unit_of_work,
            claims=AITaskExecutionClaims(
                repository=SqlAlchemyAITaskExecutionClaimRepository(),
            ),
            repository=SqlAlchemyAITaskProviderSendFenceRepository(),
        ),
        clock=lambda: datetime.now(timezone.utc),
    ).send_once(
        prepared=prepared, begun=begun, job_id=current.job_id,
        fencing_token=current.fencing_token,
        worker_ref=context["worker_ref"],
    )
    response.close()
    assert adapter.calls and len(adapter.calls) == 1
    with schema.connect(context["database"]) as db:
        db.execute(
            "UPDATE plm.job_leases SET lease_expires_at=acquired_at "
            "+ interval '1 microsecond' WHERE job_id=%s AND fencing_token=%s",
            (current.job_id, current.fencing_token),
        )
        db.execute(
            "UPDATE plm.job_jobs j SET lease_expires_at=l.lease_expires_at "
            "FROM plm.job_leases l WHERE j.job_id=l.job_id "
            "AND j.fencing_token=l.fencing_token AND j.job_id=%s",
            (current.job_id,),
        )

    jobs = SqlAlchemyJobLeaseRepository()
    with runtime.unit_of_work() as transaction:
        claimed = jobs.claim_next(
            transaction, worker_ref="generic-worker", lease_seconds=30,
        )
        assert claimed is None or claimed.job_id != current.job_id
    with schema.connect(context["database"]) as db:
        before = db.execute(
            "SELECT j.state,j.attempt_count,j.fencing_token,l.state,a.completed_at,"
            "i.invocation_state,t.task_state FROM plm.job_jobs j "
            "JOIN plm.job_leases l ON l.job_id=j.job_id AND l.fencing_token=j.fencing_token "
            "JOIN plm.job_attempts a ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id "
            "JOIN plm.ai_invocations i ON i.ai_invocation_id=t.current_invocation_ref "
            "WHERE j.job_id=%s", (current.job_id,),
        ).fetchone()
    assert before == (
        "RUNNING", current.attempt_no, current.fencing_token, "ACTIVE", None,
        "RUNNING", "RUNNING",
    )

    def reconciler(audit):
        return ExpiredAITaskReconciler(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyExpiredAITaskReconciliationRepository(),
            audit=audit, system_actor=actor,
        )

    try:
        reconciler(FailingAudit()).reconcile_next()
    except AITaskReconciliationError:
        pass
    else:
        raise AssertionError("Audit failure committed reconciliation")
    with schema.connect(context["database"]) as db:
        rolled_back = db.execute(
            "SELECT j.state,l.state,a.completed_at,i.invocation_state,t.task_state "
            "FROM plm.job_jobs j JOIN plm.job_leases l ON l.job_id=j.job_id "
            "AND l.fencing_token=j.fencing_token JOIN plm.job_attempts a "
            "ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref WHERE j.job_id=%s",
            (current.job_id,),
        ).fetchone()
    assert rolled_back == ("RUNNING", "ACTIVE", None, "RUNNING", "RUNNING")

    result = reconciler(
        AuditService(SqlAlchemyAuditRepository()),
    ).reconcile_next()
    assert result is not None
    assert result.prior_invocation_state == "RUNNING"
    assert result.error_code == "AI_PROVIDER_OUTCOME_UNKNOWN"
    assert not result.retryable
    assert reconciler(AuditService(
        SqlAlchemyAuditRepository(),
    )).reconcile_next() is None
    try:
        with runtime.unit_of_work() as transaction:
            jobs.retry_or_fail(
                transaction, job_id=current.job_id,
                fencing_token=current.fencing_token,
                worker_ref=context["worker_ref"],
                error_code="AI_PROVIDER_NETWORK_UNAVAILABLE",
                retryable=False, delay_seconds=0,
            )
    except JobLeaseError:
        pass
    else:
        raise AssertionError("expired worker overwrote reconciled terminal state")
    with schema.connect(context["database"]) as db:
        terminal = db.execute(
            "SELECT j.state,j.completed_at,l.state,a.error_code,a.completed_at,"
            "i.invocation_state,i.error_code,i.retryable,i.completed_at,"
            "t.task_state,t.error_code,t.retryable,t.completed_at "
            "FROM plm.job_jobs j JOIN plm.job_leases l ON l.job_id=j.job_id "
            "AND l.fencing_token=j.fencing_token JOIN plm.job_attempts a "
            "ON a.job_id=j.job_id AND a.fencing_token=j.fencing_token "
            "JOIN plm.ai_tasks t ON t.job_ref=j.job_id JOIN plm.ai_invocations i "
            "ON i.ai_invocation_id=t.current_invocation_ref WHERE j.job_id=%s",
            (current.job_id,),
        ).fetchone()
        event = db.execute(
            "SELECT outcome,reason_code,target_version_id FROM plm.aud_events "
            "WHERE action='AI_TASK_EXECUTION_RECONCILED' AND trace_id=%s",
            (prepared.grant.trace_id,),
        ).fetchone()
    assert terminal[0] == "FAILED" and terminal[1] == terminal[4]
    assert terminal[2:5] == (
        "EXPIRED", "AI_PROVIDER_OUTCOME_UNKNOWN", result.completed_at,
    )
    assert terminal[5:9] == (
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
        result.completed_at,
    )
    assert terminal[9:13] == (
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", False,
        result.completed_at,
    )
    assert event == (
        "FAILED", "AI_PROVIDER_OUTCOME_UNKNOWN", begun.ai_invocation_id,
    )
    assert len(adapter.calls) == 1
    assert all(not any(value) for value in decryptor.buffers)
    print(
        "AI_04_A06_P08_P03_EXPIRED_TASK_RECONCILIATION_PASS: "
        "Win11/PostgreSQL18.6 excluded one expired fenced AI Job from generic "
        "reclaim, rolled back owner reconciliation on Audit failure, then atomically "
        "expired Lease and terminalized Job/Attempt/RUNNING Invocation/Task as "
        "non-retryable AI_PROVIDER_OUTCOME_UNKNOWN; old Worker overwrite rejected, "
        "one synthetic Adapter call only, zero real Provider network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p08p03_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
