"""Disposable PG18 authorized activation and immutable replay proof."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plm_assistant.modules.ai.application.activate_provider import (
    AIProviderActivationError, AIProviderActivationService, ActivateAIProvider,
)
from plm_assistant.modules.ai.application.provider_activation_proof import ProviderActivationProofService
from plm_assistant.modules.ai.infrastructure.provider_activation_proof_repository import SqlAlchemyProviderActivationProofRepository
from plm_assistant.modules.ai.infrastructure.provider_activation_repository import SqlAlchemyAIProviderActivationRepository
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


parent = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p05-a01-job-read" / "verify.py"))
connect = parent["connect"]
submit_helpers = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p03-a02-provider-test-submit" / "verify.py"))


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit outage")


def after_success(*, runtime, name, actor, request, ref, guard, token,
                  result_id, policies, secret):
    del ref, result_id
    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (request.secret_version_id,))
            db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (request.secret_version_id, secret))
        submit_helpers["seed_user"](db, "Synthetic Activation Member", "NONE", b"m" * 32)
    proof = ProviderActivationProofService(
        current=SqlAlchemyAIProviderTestSource(), secrets=SqlAlchemyAIProviderSecretProof(),
        policies=policies, latest=SqlAlchemyProviderActivationProofRepository(),
        license_guard=guard,
    )
    access = SqlAlchemyLicenseImportAccess()
    receipts = SqlAlchemyIdempotencyReceipts()
    repository = SqlAlchemyAIProviderActivationRepository()

    def service(audit=None):
        return AIProviderActivationService(
            unit_of_work=runtime.unit_of_work, access=access, license_guard=guard,
            proof=proof, repository=repository, receipts=receipts,
            audit=audit or AuditService(SqlAlchemyAuditRepository()),
        )

    def expect(code, command, selected=None):
        try:
            (selected or service()).activate(command)
        except AIProviderActivationError as exc:
            assert exc.code == code, (exc.code, code)
        else:
            raise AssertionError(f"expected {code}")

    original = ActivateAIProvider(token, b"c" * 32, uuid.uuid4(),
                                  request.provider_id, 0, str(uuid.uuid4()))
    expect("AUTH_ACCESS_DENIED", ActivateAIProvider(
        b"x" * 32, b"c" * 32, uuid.uuid4(), request.provider_id, 0,
        str(uuid.uuid4())))
    expect("AUTH_ACCESS_DENIED", ActivateAIProvider(
        b"m" * 32, b"c" * 32, uuid.uuid4(), request.provider_id, 0,
        str(uuid.uuid4())))
    guard.enabled = False
    expect("LICENSE_OPERATION_DENIED", original)
    guard.enabled = True
    with ThreadPoolExecutor(max_workers=2) as workers:
        attempts = list(workers.map(lambda _: service().activate(original), range(2)))
    assert attempts[0] == attempts[1]
    first = attempts[0]
    assert (first.state, first.lock_version, first.etag,
            first.provider_id, first.config_id) == (
            "ACTIVE", 1, '"v1"', request.provider_id, request.config_id)
    with connect(name) as db:
        assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (request.provider_id,)).fetchone() == ("ACTIVE", 1)
        assert db.execute("SELECT count(*) FROM plm.ai_provider_activation_results WHERE ai_provider_id=%s", (request.provider_id,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_ACTIVATED' AND target_object_id=%s", (request.provider_id,)).fetchone()[0] == 1
        db.execute("UPDATE plm.ai_providers SET provider_state='SUSPENDED',lock_version=lock_version+1 WHERE ai_provider_id=%s", (request.provider_id,))
    assert service().activate(original) == first
    with connect(name) as db:
        assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (request.provider_id,)).fetchone() == ("SUSPENDED", 2)
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_ACTIVATED' AND target_object_id=%s", (request.provider_id,)).fetchone()[0] == 1
    expect("CONFLICT_VERSION", ActivateAIProvider(token, b"c" * 32, uuid.uuid4(),
        request.provider_id, 0, str(uuid.uuid4())))
    next_command = ActivateAIProvider(token, b"c" * 32, uuid.uuid4(),
                                      request.provider_id, 2, str(uuid.uuid4()))
    with connect(name) as db:
        db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (secret,))
    expect("AI_PROVIDER_SECRET_UNAVAILABLE", next_command)
    with connect(name) as db:
        db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (secret,))
    expect("AI_PROVIDER_UNAVAILABLE", next_command, service(FailedAudit()))
    with connect(name) as db:
        assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (request.provider_id,)).fetchone() == ("SUSPENDED", 2)
        assert db.execute("SELECT count(*) FROM plm.ai_provider_activation_results WHERE ai_provider_id=%s", (request.provider_id,)).fetchone()[0] == 1
    second = service().activate(next_command)
    assert (second.state, second.lock_version, second.etag) == ("ACTIVE", 3, '"v3"')
    assert service().activate(next_command) == second
    expect("CONFLICT_IDEMPOTENCY", ActivateAIProvider(token, b"c" * 32,
        uuid.uuid4(), request.provider_id, 1, next_command.idempotency_key))
    with connect(name) as db:
        assert db.execute("SELECT count(*) FROM plm.ai_provider_activation_results WHERE ai_provider_id=%s", (request.provider_id,)).fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_ACTIVATED' AND target_object_id=%s", (request.provider_id,)).fetchone()[0] == 2
    print("PASS: PG18 admin/License, atomic ACTIVE/Audit/snapshot/receipt, suspended historical replay, version and rollback")


if __name__ == "__main__":
    parent["main"](after_success=after_success)
