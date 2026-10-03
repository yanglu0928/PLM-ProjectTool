"""Windows 11/PostgreSQL 18 proof for ordered AI Provider send orchestration."""

from __future__ import annotations

import hashlib
import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderResponse,
    AIProviderResponseObservation,
)
from plm_assistant.modules.ai.application.send_provider_request import (
    AITaskProviderSendService,
)
from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
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


class SyntheticDecryptor:
    def __init__(self, expected_version: uuid.UUID) -> None:
        self.expected_version = expected_version
        self.buffers: list[bytearray] = []

    def decrypt(self, envelope) -> bytearray:
        assert envelope.secret_version_id == self.expected_version
        value = bytearray(b"synthetic-task-key-not-for-network")
        self.buffers.append(value)
        return value


class FixedSystemActor:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id

    def assert_current(self) -> uuid.UUID:
        return self.actor_id


class CountingPreSend:
    def __init__(self, service) -> None:
        self.service = service
        self.results = []

    def authorize(self, **values):
        result = self.service.authorize(**values)
        self.results.append(result)
        return result


class SyntheticAdapter:
    def __init__(self, expected_key: bytes) -> None:
        self.expected_key = expected_key
        self.calls = []

    def send(self, **values) -> AIProviderResponse:
        assert values["key"].tobytes() == self.expected_key
        self.calls.append({key: value for key, value in values.items() if key != "key"})
        body = bytearray(b'{"choices":[{"message":{"content":"{}"}}]}')
        return AIProviderResponse(body, AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body), 10, 2, 5, "STOP",
        ))


class SyntheticFence:
    def __init__(self) -> None:
        self.calls = []

    def fence(self, **values) -> None:
        self.calls.append(values)


def validate(context: dict[str, object]) -> None:
    prepared = context["prepared_invocation"]
    begun = context["begun_invocation"]
    current = context["current_claim"]
    initial = context["authorized_send"]
    runtime = context["runtime"]
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p06p05p04_schema_helper",
    )
    username = "synthetic-ai-send-worker-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id",
            (username, username),
        ).fetchone()[0]

    audit = AITaskProviderSecretAccessAudit(
        unit_of_work=runtime.unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=FixedSystemActor(system_id),
    )
    decryptor = SyntheticDecryptor(initial.route.secret_version_id)
    secrets = SecretResolver(
        SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), decryptor, audit,
    )
    pre_send = CountingPreSend(context["pre_send_service"])
    adapter = SyntheticAdapter(b"synthetic-task-key-not-for-network")
    fence = SyntheticFence()
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
    try:
        assert response.view().tobytes() == (
            b'{"choices":[{"message":{"content":"{}"}}]}'
        )
    finally:
        response.close()
    assert len(pre_send.results) == 2
    assert pre_send.results[0].route == pre_send.results[1].route
    assert len(adapter.calls) == 1
    assert len(fence.calls) == 1
    assert adapter.calls[0]["route"] == pre_send.results[1].route
    assert adapter.calls[0]["proof"] == pre_send.results[1].proof
    assert len(decryptor.buffers) == 1
    assert all(not any(value) for value in decryptor.buffers)

    with schema.connect(context["database"]) as db:
        rows = db.execute(
            "SELECT event_scope,target_project_id,actor_type,actor_id,"
            "original_actor_id,outcome,target_object_id,target_version_id,"
            "after_state FROM plm.aud_events WHERE trace_id=%s "
            "AND action='AI_PROVIDER_SECRET_ACCESS' ORDER BY occurred_at,audit_event_id",
            (prepared.grant.trace_id,),
        ).fetchall()
    assert rows == [(
        "PROJECT", prepared.grant.project_id, "SYSTEM", system_id,
        prepared.grant.requested_by, "SUCCESS", initial.route.secret_ref,
        initial.route.secret_version_id, "AI_TASK_SEND",
    )]
    print(
        "AI_04_A06_P06_P05_P04_PROVIDER_SEND_ORCHESTRATION_PASS: "
        "Win11/PostgreSQL18.6 performed initial pre-send, exact current "
        "SecretVersion read/decrypt/Project audit, second pre-send, stable Route/Proof "
        "identity check and one synthetic Adapter call in order; the plaintext key and "
        "owned response were zeroized; zero real Provider network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p06p05p04_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
