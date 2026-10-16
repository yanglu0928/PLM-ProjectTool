"""Disposable PG18 current activation proof; no activation write or egress."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.provider_activation_proof import (
    ProviderActivationProofError, ProviderActivationProofService,
)
from plm_assistant.modules.ai.infrastructure.provider_activation_proof_repository import (
    SqlAlchemyProviderActivationProofRepository,
)
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobQueue, AIProviderTestJobRequest
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import SqlAlchemyAIProviderTestClaimRepository
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof


parent = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p05-a01-job-read" / "verify.py"))
connect = parent["connect"]


def after_success(*, runtime, name, actor, request, ref, guard, token,
                  result_id, policies, secret):
    del token
    latest = SqlAlchemyProviderActivationProofRepository()
    service = ProviderActivationProofService(
        current=SqlAlchemyAIProviderTestSource(),
        secrets=SqlAlchemyAIProviderSecretProof(), policies=policies,
        latest=latest, license_guard=guard,
    )

    def require(selected=service):
        with runtime.unit_of_work() as tx:
            return selected.require_locked(tx, provider_id=request.provider_id,
                                           trace_id=uuid.uuid4())

    def expect(code, selected=service):
        try:
            require(selected)
        except ProviderActivationProofError as exc:
            assert exc.code == code, (exc.code, code)
        else:
            raise AssertionError(f"expected {code}")

    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (request.secret_version_id,))
            db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (request.secret_version_id, secret))
    proof = require()
    assert (proof.provider_id, proof.config_id, proof.secret_version_id,
            proof.result_id, proof.job_id) == (
            request.provider_id, request.config_id, request.secret_version_id,
            result_id, ref.job_id)

    changed_policies = EndpointProbeRegistry({"endpoint.synthetic.v1": EndpointProbePolicy(
        "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
        "https://changed.example.test/v1/chat", "synthetic-chat", "cn-beijing", "SYNTHETIC")})
    altered = ProviderActivationProofService(
        current=SqlAlchemyAIProviderTestSource(), secrets=SqlAlchemyAIProviderSecretProof(),
        policies=changed_policies, latest=latest, license_guard=guard)
    expect("AI_PROVIDER_TEST_REQUIRED", altered)

    with connect(name) as db:
        db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (secret,))
    expect("AI_PROVIDER_SECRET_UNAVAILABLE")
    with connect(name) as db:
        db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (secret,))

    new_config = uuid.uuid4()
    with connect(name) as db:
        with db.transaction():
            db.execute("INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,%s,2,'OPENAI_COMPATIBLE','Synthetic Read V2','endpoint.synthetic.v1',%s,'cn-beijing','SYNTHETIC',true,false,false,false,%s)", (new_config, request.provider_id, secret, actor))
            db.execute("UPDATE plm.ai_providers SET current_config_version_ref=%s WHERE ai_provider_id=%s", (new_config, request.provider_id))
    expect("AI_PROVIDER_TEST_REQUIRED")
    with connect(name) as db:
        db.execute("UPDATE plm.ai_providers SET current_config_version_ref=%s WHERE ai_provider_id=%s", (request.config_id, request.provider_id))
    assert require().result_id == result_id

    new_version = uuid.uuid4()
    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.plt_secret_versions SET retired_at=statement_timestamp() WHERE secret_version_id=%s", (request.secret_version_id,))
            db.execute("INSERT INTO plm.plt_secret_versions(secret_version_id,secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by,activated_at) VALUES (%s,%s,2,%s,'{}'::jsonb,'synthetic-only',%s,statement_timestamp())", (new_version, secret, b"y", actor))
            db.execute("UPDATE plm.plt_secret_records SET current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s", (new_version, secret))
    expect("AI_PROVIDER_TEST_REQUIRED")

    queue = AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository())
    failed = AIProviderTestJobRequest(uuid.uuid4(), request.provider_id, request.config_id,
        1, new_version, actor, uuid.uuid4(), request.policy_sha256)
    with runtime.unit_of_work() as tx:
        failed_ref = queue.enqueue(tx, request=failed)
        tx.commit()
    claims = SqlAlchemyAIProviderTestClaimRepository()
    with runtime.unit_of_work() as tx:
        claim = claims.claim_next(tx, worker_ref="synthetic-failure-worker", lease_seconds=20)
        assert claim is not None and claim.job_id == failed_ref.job_id
        tx.commit()
    with connect(name) as db:
        with db.transaction():
            db.execute("UPDATE plm.job_leases SET state='RELEASED' WHERE job_id=%s", (failed_ref.job_id,))
            db.execute("UPDATE plm.job_attempts SET completed_at=statement_timestamp(),error_code='PROBE_HTTP_REJECTED' WHERE job_id=%s", (failed_ref.job_id,))
            db.execute("UPDATE plm.job_jobs SET state='FAILED',completed_at=statement_timestamp(),lease_expires_at=NULL WHERE job_id=%s", (failed_ref.job_id,))
            db.execute("INSERT INTO plm.ai_provider_probe_results(ai_provider_id,provider_config_version_id,secret_record_id,secret_version_id,job_id,probe_id,policy_sha256,outcome,failure_code,attempt_no,fencing_token,observed_at) VALUES (%s,%s,%s,%s,%s,'CHAT_CONNECTIVITY_V1',%s,'FAILED','PROBE_HTTP_REJECTED',1,1,statement_timestamp()+interval '1 second')", (request.provider_id, request.config_id, secret, new_version, failed_ref.job_id, request.policy_sha256))
    with runtime.unit_of_work() as tx:
        assert latest.latest_success(tx, provider_id=request.provider_id) is None
    expect("AI_PROVIDER_TEST_REQUIRED")
    print("PASS: PG18 latest success, policy/config/Secret changes and newer failure reject stale activation proof")


if __name__ == "__main__":
    parent["main"](after_success=after_success)
