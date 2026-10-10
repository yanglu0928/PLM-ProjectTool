"""Disposable PostgreSQL proof of atomic Provider probe success publication."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightService
from plm_assistant.modules.ai.application.publish_provider_probe_success import (
    ProviderProbePublicationError, ProviderProbeSuccessPublisher,
)
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeObservation
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
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import SqlAlchemyAIProviderTestClaimRepository
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from types import SimpleNamespace


helpers = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p04-a02-preflight" / "verify.py"))
connect = helpers["connect"]
seed_user = helpers["seed_user"]
seed_secret = helpers["seed_secret"]
Guard = helpers["Guard"]
CSRF = helpers["CSRF"]
HOST, PORT, USER = helpers["HOST"], helpers["PORT"], helpers["USER"]


def expect(code, call):
    try:
        call()
    except ProviderProbePublicationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


class FailAfterFinish:
    def finish(self, transaction, **kwargs):
        SqlAlchemyJobLeaseRepository().finish(transaction, **kwargs)
        raise JobLeaseError("synthetic-after-finish")


def main():
    name = "ai01a05p04a04p01_" + uuid.uuid4().hex[:8]
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
                    secret, secret_version = seed_secret(db, actor)
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
                source = SqlAlchemyAIProviderTestSource()
                claims = AIProviderTestClaims(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyAIProviderTestClaimRepository(),
                )
                submitter = AIProviderTestSubmitService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    license_guard=guard, source=source, secret_proof=proof,
                    probe_registry=registry,
                    queue=AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository()),
                    receipts=receipts, audit=audit,
                )
                preflight = ProviderTestPreflightService(
                    unit_of_work=runtime.unit_of_work, claims=claims,
                    license_guard=guard, source=source, secret_proof=proof,
                    probe_registry=registry,
                )
                store = SqlAlchemyProviderProbeResultRepository()
                jobs = SqlAlchemyJobLeaseRepository()
                probe_audit = ProviderProbeAudit(
                    system_actor=SimpleNamespace(assert_current=lambda: uuid.UUID(int=1)),
                    audit=audit,
                )

                def submit_claim():
                    trace = uuid.uuid4()
                    job = submitter.submit(SubmitAIProviderTest(
                        token, CSRF, trace, provider, 0, str(uuid.uuid4()),
                    ))
                    claim = claims.claim_next(worker_ref="publisher-worker", lease_seconds=60)
                    assert claim.job_id == job.job_id
                    return claim, trace

                def publisher(job_finisher=jobs):
                    return ProviderProbeSuccessPublisher(
                        unit_of_work=runtime.unit_of_work, preflight=preflight,
                        store=store, jobs=job_finisher, audit=probe_audit,
                    )

                def publish(claim, trace, job_finisher=jobs):
                    return publisher(job_finisher).publish(
                        observation=ProviderProbeObservation(claim.job_id, claim.fencing_token),
                        worker_ref="publisher-worker", trace_id=trace,
                    )

                first, first_trace = submit_claim()
                expect("JOB_LEASE_LOST", lambda: publisher().publish(
                    observation=ProviderProbeObservation(first.job_id, first.fencing_token + 1),
                    worker_ref="publisher-worker", trace_id=first_trace,
                ))
                expect("JOB_LEASE_LOST", lambda: publish(first, first_trace, FailAfterFinish()))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == 0
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (first.job_id,)).fetchone()[0] == "RUNNING"
                result_id = publish(first, first_trace)
                with connect(name) as db:
                    row = db.execute(
                        "SELECT outcome,failure_code,provider_config_version_id,secret_version_id,"
                        "attempt_no,fencing_token FROM plm.ai_provider_probe_results WHERE probe_result_id=%s",
                        (result_id,),
                    ).fetchone()
                    assert row == ("SUCCEEDED", None, first.config_id, secret_version, 1, 1)
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (first.job_id,)).fetchone()[0] == "SUCCEEDED"
                    assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s", (first.job_id,)).fetchone()[0] == "RELEASED"
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_SUCCEEDED'", (first_trace,)).fetchone()[0] == 1
                expect("JOB_LEASE_LOST", lambda: publish(first, first_trace))

                second, second_trace = submit_claim()
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',"
                               "lock_version=lock_version+1 WHERE secret_record_id=%s", (secret,))
                expect("AI_PROVIDER_SECRET_CHANGED", lambda: publish(second, second_trace))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == 1
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (second.job_id,)).fetchone()[0] == "RUNNING"
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',"
                               "lock_version=lock_version+1 WHERE secret_record_id=%s", (secret,))
                publish(second, second_trace)

                third, third_trace = submit_claim()
                with connect(name) as db:
                    with db.transaction():
                        prior_id = db.execute("SELECT current_config_version_ref FROM plm.ai_providers WHERE ai_provider_id=%s", (provider,)).fetchone()[0]
                        new_id = db.execute(
                            "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) "
                            "SELECT ai_provider_id,2,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by "
                            "FROM plm.ai_provider_config_versions WHERE provider_config_version_id=%s RETURNING provider_config_version_id", (prior_id,),
                        ).fetchone()[0]
                        db.execute("UPDATE plm.ai_providers SET current_config_version_ref=%s,lock_version=lock_version+1 WHERE ai_provider_id=%s", (new_id, provider))
                expect("AI_PROVIDER_CONFIG_CHANGED", lambda: publish(third, third_trace))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == 2
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (third.job_id,)).fetchone()[0] == "RUNNING"
                print("PASS: isolated PG18 atomic result/Job success, rollback, stale fencing, Secret/config change")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
