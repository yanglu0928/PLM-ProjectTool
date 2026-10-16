"""Windows 11/PostgreSQL 18 proof for AI Task-bound Secret access audit."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from plm_assistant.modules.ai.infrastructure.task_provider_secret_audit import (
    AITaskProviderSecretAccessAudit,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError,
    SecretConsumer,
    SecretEnvelope,
    SecretPurpose,
    SecretRef,
    SecretResolver,
    SecretState,
)
from plm_assistant.modules.platform.application.trace_context import trace_scope


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticStore:
    def __init__(self, envelope: SecretEnvelope) -> None:
        self.envelope = envelope

    def load(self, secret_ref: SecretRef) -> SecretEnvelope | None:
        if secret_ref != self.envelope.secret_ref:
            return None
        return self.envelope


class SyntheticDecryptor:
    def __init__(self) -> None:
        self.buffers: list[bytearray] = []

    def decrypt(self, _envelope: SecretEnvelope) -> bytearray:
        value = bytearray(b"synthetic-task-key-not-for-network")
        self.buffers.append(value)
        return value


class FixedSystemActor:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id

    def assert_current(self) -> uuid.UUID:
        return self.actor_id


def validate(context: dict[str, object]) -> None:
    prepared = context["prepared_invocation"]
    send = context["authorized_send"]
    route = send.route
    grant = prepared.grant
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p06p05p03_schema_helper",
    )
    username = "synthetic-ai-task-audit-" + uuid.uuid4().hex[:12]
    with schema.connect(context["database"]) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id",
            (username, username),
        ).fetchone()[0]

    audit = AITaskProviderSecretAccessAudit(
        unit_of_work=context["runtime"].unit_of_work,
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=FixedSystemActor(system_id),
    )
    envelope = SecretEnvelope(
        secret_ref=SecretRef(route.secret_ref),
        purpose=SecretPurpose.AI_PROVIDER_KEY,
        state=SecretState.ACTIVE,
        allowed_consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
        version_no=1,
        encrypted_payload=b"synthetic-ciphertext",
        encryption_metadata=b"{}",
        key_provider_ref="synthetic-only",
        secret_version_id=route.secret_version_id,
    )
    decryptor = SyntheticDecryptor()
    resolver = SecretResolver(SyntheticStore(envelope), decryptor, audit)
    with audit.bind(prepared, send), trace_scope(str(grant.trace_id)):
        with resolver.use(
            SecretRef(route.secret_ref),
            SecretConsumer.AI_PROVIDER_ADAPTER,
            expected_version_id=route.secret_version_id,
        ) as key:
            assert key.tobytes() == b"synthetic-task-key-not-for-network"
        try:
            with resolver.use(
                SecretRef(route.secret_ref),
                SecretConsumer.AI_PROVIDER_ADAPTER,
                expected_version_id=uuid.uuid4(),
            ):
                raise AssertionError("wrong SecretVersion authorized")
        except SecretAccessError:
            pass
    assert len(decryptor.buffers) == 1
    assert all(not any(value) for value in decryptor.buffers)

    with schema.connect(context["database"]) as db:
        rows = db.execute(
            "SELECT event_scope,target_project_id,actor_type,actor_id,"
            "original_actor_id,outcome,target_owner_module,target_object_type,"
            "target_object_id,target_version_id,after_state FROM plm.aud_events "
            "WHERE trace_id=%s AND action='AI_PROVIDER_SECRET_ACCESS' "
            "ORDER BY occurred_at,audit_event_id",
            (grant.trace_id,),
        ).fetchall()
    assert len(rows) == 2
    assert [row[5] for row in rows] == ["SUCCESS", "DENIED"]
    for row in rows:
        assert row[:5] == (
            "PROJECT", grant.project_id, "SYSTEM", system_id, grant.requested_by,
        )
        assert row[6:] == (
            "platform", "PLT-02", route.secret_ref,
            route.secret_version_id, "AI_TASK_SEND",
        )
    print(
        "AI_04_A06_P06_P05_P03_TASK_SECRET_AUDIT_PASS: Win11/PostgreSQL18.6 "
        "bound the exact Task/Invocation/Job/fencing/Route/SecretVersion to a minimal "
        "ContextVar scope; SecretResolver persisted Project-scoped SYSTEM/original-user "
        "GRANTED and DENIED evidence, rejected version drift before decrypt, and zeroized "
        "the only plaintext buffer; zero Provider network I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p06-p03-pre-send-owner", "p06p05p03_pre_send_helper",
    )
    helper.main(after_authorized=validate)


if __name__ == "__main__":
    main()
