"""Disposable PG18 proof of Provider probe retries, final failure and audit."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.publish_provider_probe_failure import (
    ProviderProbeFailureError, ProviderProbeFailurePublisher,
)
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeExecutionError
from plm_assistant.modules.ai.application.submit_provider_test import AIProviderTestSubmitService, SubmitAIProviderTest
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.ai.infrastructure.provider_probe_result_repository import SqlAlchemyProviderProbeResultRepository
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaims
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobQueue
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import SqlAlchemyAIProviderTestClaimRepository
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


helpers = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p04-a02-preflight" / "verify.py"))
connect = helpers["connect"]
seed_user = helpers["seed_user"]
seed_secret = helpers["seed_secret"]
Guard = helpers["Guard"]
CSRF = helpers["CSRF"]
HOST, PORT, USER = helpers["HOST"], helpers["PORT"], helpers["USER"]


class FailingAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit outage")


def expect(code, call):
    try:
        call()
    except ProviderProbeFailureError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "ai01a05p04a04p02_" + uuid.uuid4().hex[:8]
    token = b"a" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, token)
                    secret, version = seed_secret(db, actor)
                guard = Guard()
                access = SqlAlchemyLicenseImportAccess()
                proof = SqlAlchemyAIProviderSecretProof()
                receipts = SqlAlchemyIdempotencyReceipts()
                audit = AuditService(SqlAlchemyAuditRepository())
                provider = AIProviderCreateService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, secret_proof=proof,
                    repository=SqlAlchemyAIProviderCreateRepository(),
                    receipts=receipts, audit=audit,
                ).create(CreateAIProvider(
                    token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "SYNTHETIC", frozenset({ProviderCapability.CHAT}),
                    str(uuid.uuid4()),
                ))
                registry = EndpointProbeRegistry({"endpoint.synthetic.v1": EndpointProbePolicy(
                    "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
                    "https://probe.example.test/v1/chat", "synthetic-chat",
                    "cn-beijing", "SYNTHETIC",
                )})
                claims = AIProviderTestClaims(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyAIProviderTestClaimRepository(),
                )
                submitter = AIProviderTestSubmitService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, source=SqlAlchemyAIProviderTestSource(),
                    secret_proof=proof, probe_registry=registry,
                    queue=AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository()),
                    receipts=receipts, audit=audit,
                )
                actor_source = SimpleNamespace(assert_current=lambda: uuid.UUID(int=1))

                def publisher(audit_service=audit):
                    return ProviderProbeFailurePublisher(
                        unit_of_work=runtime.unit_of_work, claims=claims,
                        jobs=SqlAlchemyJobLeaseRepository(),
                        results=SqlAlchemyProviderProbeResultRepository(),
                        audit=ProviderProbeAudit(system_actor=actor_source, audit=audit_service),
                    )

                def submit_claim():
                    trace = uuid.uuid4()
                    job = submitter.submit(SubmitAIProviderTest(
                        token, CSRF, trace, provider, 0, str(uuid.uuid4()),
                    ))
                    claim = claims.claim_next(worker_ref="failure-worker", lease_seconds=60)
                    assert claim.job_id == job.job_id
                    return job, claim, trace

                def fail(claim, trace, code, audit_service=audit):
                    return publisher(audit_service).publish(
                        job_id=claim.job_id, fencing_token=claim.fencing_token,
                        worker_ref="failure-worker", trace_id=trace,
                        error=ProviderProbeExecutionError(code),
                    )

                job, first, trace = submit_claim()
                for claim, expected_delay in ((first, 5),):
                    outcome = fail(claim, trace, "PROBE_NETWORK_UNAVAILABLE")
                    assert outcome.job_state == "RETRY_WAIT" and outcome.result_id is None
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results WHERE job_id=%s", (job.job_id,)).fetchone()[0] == 0
                        row = db.execute("SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s", (job.job_id,)).fetchone()
                        assert row == ("RETRY_WAIT", 1)
                        assert db.execute("SELECT error_code FROM plm.job_attempts WHERE job_id=%s AND attempt_no=1", (job.job_id,)).fetchone()[0] == "PROBE_NETWORK_UNAVAILABLE"
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_RETRY'", (trace,)).fetchone()[0] == 1
                        db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp() WHERE job_id=%s", (job.job_id,))
                second = claims.claim_next(worker_ref="failure-worker", lease_seconds=60)
                assert (second.job_id, second.attempt_no, second.fencing_token) == (job.job_id, 2, 2)
                expect("JOB_LEASE_LOST", lambda: fail(first, trace, "PROBE_NETWORK_UNAVAILABLE"))
                outcome = fail(second, trace, "PROBE_NETWORK_UNAVAILABLE")
                assert outcome.job_state == "RETRY_WAIT" and outcome.result_id is None
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results WHERE job_id=%s", (job.job_id,)).fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_RETRY'", (trace,)).fetchone()[0] == 2
                    db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp() WHERE job_id=%s", (job.job_id,))
                third = claims.claim_next(worker_ref="failure-worker", lease_seconds=60)
                assert (third.job_id, third.attempt_no, third.fencing_token) == (job.job_id, 3, 3)
                outcome = fail(third, trace, "PROBE_NETWORK_UNAVAILABLE")
                assert outcome.job_state == "FAILED" and outcome.result_id is not None
                with connect(name) as db:
                    row = db.execute(
                        "SELECT outcome,failure_code,secret_record_id,secret_version_id,attempt_no,fencing_token "
                        "FROM plm.ai_provider_probe_results WHERE job_id=%s", (job.job_id,),
                    ).fetchone()
                    assert row == ("FAILED", "PROBE_NETWORK_UNAVAILABLE", secret, version, 3, 3)
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (job.job_id,)).fetchone()[0] == "FAILED"
                    assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=3", (job.job_id,)).fetchone()[0] == "RELEASED"
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_FAILED'", (trace,)).fetchone()[0] == 1
                expect("JOB_LEASE_LOST", lambda: fail(third, trace, "PROBE_NETWORK_UNAVAILABLE"))

                fatal_job, fatal_claim, fatal_trace = submit_claim()
                expect("AI_PROVIDER_UNAVAILABLE", lambda: fail(
                    fatal_claim, fatal_trace, "PROBE_HTTP_REJECTED", FailingAudit(),
                ))
                with connect(name) as db:
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (fatal_job.job_id,)).fetchone()[0] == "RUNNING"
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results WHERE job_id=%s", (fatal_job.job_id,)).fetchone()[0] == 0
                fatal = fail(fatal_claim, fatal_trace, "PROBE_HTTP_REJECTED")
                assert fatal.job_state == "FAILED" and fatal.result_id is not None
                with connect(name) as db:
                    assert db.execute("SELECT error_code FROM plm.job_attempts WHERE job_id=%s", (fatal_job.job_id,)).fetchone()[0] == "PROBE_HTTP_REJECTED"
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results WHERE job_id=%s", (fatal_job.job_id,)).fetchone()[0] == 1
                print("PASS: isolated PG18 three-attempt retry/final proof, stale fence, fatal, Audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
