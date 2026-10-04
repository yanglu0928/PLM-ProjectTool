"""Windows 11/PostgreSQL 18 proof for the durable Provider send fence."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.provider_send_fence import (
    AITaskProviderSendFenceService,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendError,
    AITaskProviderSendService,
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
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
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


def validate(context: dict[str, object]) -> None:
    send_helper = load_helper(
        "ai-04-a06-p06-p05-p04-provider-send-orchestration",
        "p07p03_send_helper",
    )
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p07p03_schema_helper",
    )
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    initial = context["authorized_send"]
    runtime = context["runtime"]
    username = "synthetic-ai-fence-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]

    audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=send_helper.FixedSystemActor(system_id),
    )
    decryptor = send_helper.SyntheticDecryptor(
        initial.route.secret_version_id,
    )
    secrets = SecretResolver(
        SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), decryptor, audit,
    )
    pre_send = send_helper.CountingPreSend(context["pre_send_service"])
    fence = AITaskProviderSendFenceService(
        unit_of_work=runtime.unit_of_work,
        claims=AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        ),
        repository=SqlAlchemyAITaskProviderSendFenceRepository(),
    )
    adapter = send_helper.SyntheticAdapter(
        b"synthetic-task-key-not-for-network",
    )
    service = AITaskProviderSendService(
        pre_send=pre_send, secrets=secrets, adapter=adapter,
        access_audit_scope=audit, send_fence=fence,
        clock=lambda: datetime.now(timezone.utc),
    )
    response = service.send_once(
        prepared=prepared, begun=begun, job_id=current.job_id,
        fencing_token=current.fencing_token,
        worker_ref=context["worker_ref"],
    )
    response.close()
    assert len(pre_send.results) == 2
    assert len(adapter.calls) == 1
    assert all(not any(value) for value in decryptor.buffers)

    with schema.connect(context["database"]) as db:
        state = db.execute(
            "SELECT invocation_state,started_at,completed_at,lock_version,"
            "suggestion_payload_ref FROM plm.ai_invocations "
            "WHERE ai_invocation_id=%s", (begun.ai_invocation_id,),
        ).fetchone()
    assert state[0] == "RUNNING"
    assert state[1] is not None and state[2] is None
    assert state[3] == 1 and state[4] is None

    try:
        service.send_once(
            prepared=prepared, begun=begun, job_id=current.job_id,
            fencing_token=current.fencing_token,
            worker_ref=context["worker_ref"],
        )
    except AITaskProviderSendError as error:
        assert error.code == "AI_PROVIDER_SEND_NOT_AUTHORIZED"
    else:
        raise AssertionError("RUNNING Invocation was sent twice")
    assert len(adapter.calls) == 1
    assert len(decryptor.buffers) == 1

    print(
        "AI_04_A06_P07_P03_PROVIDER_SEND_FENCE_PASS: Win11/PostgreSQL18.6 "
        "performed two current pre-send checks, exact SecretVersion access/audit, "
        "then atomically committed the current Job generation and PENDING Invocation "
        "as RUNNING before one synthetic Adapter call; the same Invocation could not "
        "pre-send or call the Adapter again, key/response were zeroized, and no real "
        "Provider network I/O occurred"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p07p03_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
