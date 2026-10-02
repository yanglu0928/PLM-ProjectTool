"""Isolated PG18 + loopback TLS Provider Test Worker end-to-end proof."""

from __future__ import annotations

import json
import runpy
import ssl
import tempfile
import threading
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.probe_audit import ProviderProbeAudit
from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.provider_probe_worker import ProviderProbeOneShotWorker
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightService
from plm_assistant.modules.ai.application.publish_provider_probe_failure import ProviderProbeFailurePublisher
from plm_assistant.modules.ai.application.publish_provider_probe_success import ProviderProbeSuccessPublisher
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeRunner
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
from plm_assistant.modules.platform.application.secret_access import SecretResolver
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore


root = Path(__file__).parents[1]
helpers = runpy.run_path(str(root / "ai-01-a05-p04-a02-preflight" / "verify.py"))
tls_helpers = runpy.run_path(str(root / "ai-01-a05-p04-a03-p02-synthetic-tls" / "verify.py"))
connect = helpers["connect"]
seed_user = helpers["seed_user"]
seed_secret = helpers["seed_secret"]
Guard = helpers["Guard"]
CSRF = helpers["CSRF"]
HOST, PORT, USER = helpers["HOST"], helpers["PORT"], helpers["USER"]
create_certificates = tls_helpers["create_certificates"]
Handler = tls_helpers["Handler"]
SyntheticLoopbackTransport = tls_helpers["SyntheticLoopbackTransport"]
Decryptor = tls_helpers["Decryptor"]
SecretAudit = tls_helpers["Audit"]
SYNTHETIC_KEY = tls_helpers["SYNTHETIC_KEY"]


def main():
    name = "ai01a05p04a05_" + uuid.uuid4().hex[:10]
    token = b"a" * 32
    with tempfile.TemporaryDirectory(prefix="plm-one-shot-probe-tls-") as temp:
        ca_path, cert_path, key_path = create_certificates(Path(temp))
        Handler.mode = "ok"
        Handler.captured = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert_path), str(key_path))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
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
                        audit = AuditService(SqlAlchemyAuditRepository())
                        receipts = SqlAlchemyIdempotencyReceipts()
                        provider = AIProviderCreateService(
                            unit_of_work=runtime.unit_of_work, access=access,
                            license_guard=guard, secret_proof=proof,
                            repository=SqlAlchemyAIProviderCreateRepository(),
                            receipts=receipts, audit=audit,
                        ).create(CreateAIProvider(
                            token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                            "Synthetic Worker Provider", "endpoint.synthetic.v1", secret,
                            "cn-beijing", "SYNTHETIC",
                            frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                        ))
                        registry = EndpointProbeRegistry({
                            "endpoint.synthetic.v1": EndpointProbePolicy(
                                "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
                                "https://probe.example.test/v1/chat", "synthetic-chat",
                                "cn-beijing", "SYNTHETIC",
                            ),
                        })
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
                        decryptor = Decryptor()
                        runner = ProviderProbeRunner(
                            preflight=preflight,
                            secrets=SecretResolver(
                                SqlAlchemyEncryptedSecretStore(runtime.unit_of_work),
                                decryptor, SecretAudit(),
                            ),
                            transport=SyntheticLoopbackTransport(server.server_port, ca_path),
                        )
                        probe_audit = ProviderProbeAudit(
                            system_actor=SimpleNamespace(assert_current=lambda: uuid.UUID(int=1)),
                            audit=audit,
                        )
                        result_store = SqlAlchemyProviderProbeResultRepository()
                        jobs = SqlAlchemyJobLeaseRepository()
                        worker = ProviderProbeOneShotWorker(
                            claims=claims, runner=runner,
                            success=ProviderProbeSuccessPublisher(
                                unit_of_work=runtime.unit_of_work, preflight=preflight,
                                store=result_store, jobs=jobs, audit=probe_audit,
                            ),
                            failure=ProviderProbeFailurePublisher(
                                unit_of_work=runtime.unit_of_work, claims=claims,
                                jobs=jobs, results=result_store, audit=probe_audit,
                            ),
                        )

                        def submit():
                            trace = uuid.uuid4()
                            job = submitter.submit(SubmitAIProviderTest(
                                token, CSRF, trace, provider, 0, str(uuid.uuid4()),
                            ))
                            return job, trace

                        assert worker.run_once(worker_ref="synthetic-worker").state == "IDLE"
                        assert not Handler.captured
                        first, trace1 = submit()
                        result = worker.run_once(worker_ref="synthetic-worker")
                        assert result.state == "SUCCEEDED" and result.job_id == first.job_id
                        assert result.result_id is not None and len(Handler.captured) == 1
                        path, host, authorization, raw = Handler.captured[-1]
                        assert (path, host, authorization) == (
                            "/v1/chat", "probe.example.test", "Bearer " + SYNTHETIC_KEY.decode(),
                        )
                        assert json.loads(raw) == {
                            "model": "synthetic-chat",
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1, "stream": False,
                        }
                        with connect(name) as db:
                            assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (first.job_id,)).fetchone()[0] == "SUCCEEDED"
                            assert db.execute("SELECT outcome,secret_version_id FROM plm.ai_provider_probe_results WHERE job_id=%s", (first.job_id,)).fetchone() == ("SUCCEEDED", version)
                            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_SUCCEEDED'", (trace1,)).fetchone()[0] == 1
                        assert worker.run_once(worker_ref="synthetic-worker").state == "IDLE"
                        assert len(Handler.captured) == 1

                        Handler.mode = "redirect"
                        second, trace2 = submit()
                        result = worker.run_once(worker_ref="synthetic-worker")
                        assert result.state == "FAILED" and result.job_id == second.job_id
                        assert len(Handler.captured) == 2
                        with connect(name) as db:
                            assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s", (second.job_id,)).fetchone()[0] == "FAILED"
                            assert db.execute("SELECT outcome,failure_code FROM plm.ai_provider_probe_results WHERE job_id=%s", (second.job_id,)).fetchone() == ("FAILED", "PROBE_HTTP_REJECTED")
                            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AI_PROVIDER_TEST_FAILED'", (trace2,)).fetchone()[0] == 1
                        assert all(not any(buffer) for buffer in decryptor.buffers)
                        print("PASS: isolated PG18/loopback TLS one-shot IDLE/success/fatal, fixed probe, version binding, result/Audit")
                    finally:
                        runtime.dispose()
                finally:
                    admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                    admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
