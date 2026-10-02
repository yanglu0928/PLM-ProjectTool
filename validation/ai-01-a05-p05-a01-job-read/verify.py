"""Disposable PG18 proof of authorized Provider Test historical Job references."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path
from unittest.mock import Mock

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.provider_test_job_read_projection import ProviderTestJobReadProjection
from plm_assistant.modules.ai.infrastructure.provider_test_job_read import SqlAlchemyProviderTestJobReadRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobQueue, AIProviderTestJobRequest
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService, JobGetQuery, JobReadError
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import SqlAlchemyAIProviderTestClaimRepository
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


helpers = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p04-a02-preflight" / "verify.py"))
connect, seed_user, Guard = helpers["connect"], helpers["seed_user"], helpers["Guard"]
HOST, PORT, USER = helpers["HOST"], helpers["PORT"], helpers["USER"]


def expect(code, call):
    try:
        call()
    except JobReadError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "ai01a05p05a01_" + uuid.uuid4().hex[:10]
    token = b"a" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, token)
                queue = AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository())
                request = AIProviderTestJobRequest(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
                    1, uuid.uuid4(), actor, uuid.uuid4(), b"p" * 32)
                with runtime.unit_of_work() as tx:
                    ref = queue.enqueue(tx, request=request)
                    tx.commit()
                guard = Guard()
                reader = AuthorizedJobReadService(
                    unit_of_work=runtime.unit_of_work,
                    project_access=Mock(), deployment_access=SqlAlchemyDeploymentReadAccess(),
                    projects=Mock(), license_guard=guard,
                    repository=SqlAlchemyJobReadRepository(),
                    owners={("ai", "AI_PROVIDER_TEST"): ProviderTestJobReadProjection(
                        repository=SqlAlchemyProviderTestJobReadRepository())},
                )
                query = JobGetQuery(token, None, uuid.uuid4(), ref.job_id)
                pending = reader.get(query)
                assert pending.facts.state == "PENDING" and pending.owner.result_id is None
                expect("AUTH_ACCESS_DENIED", lambda: reader.get(JobGetQuery(
                    b"x" * 32, None, uuid.uuid4(), ref.job_id)))
                with connect(name) as db:
                    db.execute("UPDATE plm.job_outbox_events SET payload_refs='{}'::jsonb WHERE event_id=%s", (ref.event_id,))
                expect("JOB_UNAVAILABLE", lambda: reader.get(query))
                with connect(name) as db:
                    db.execute("UPDATE plm.job_outbox_events SET payload_refs=(SELECT payload_refs || jsonb_build_object('job_id',job_id::text) FROM plm.job_jobs WHERE job_id=%s) WHERE event_id=%s", (ref.job_id, ref.event_id))
                assert reader.get(query).owner.result_id is None
                claims = SqlAlchemyAIProviderTestClaimRepository()
                with runtime.unit_of_work() as tx:
                    claim = claims.claim_next(tx, worker_ref="synthetic-read-worker", lease_seconds=20)
                    assert claim is not None and claim.job_id == ref.job_id
                    tx.commit()
                with connect(name) as db:
                    db.execute("UPDATE plm.job_leases SET state='RELEASED' WHERE job_id=%s", (ref.job_id,))
                    db.execute("UPDATE plm.job_attempts SET completed_at=statement_timestamp() WHERE job_id=%s", (ref.job_id,))
                    db.execute("UPDATE plm.job_jobs SET state='SUCCEEDED',completed_at=statement_timestamp(),lease_expires_at=NULL WHERE job_id=%s", (ref.job_id,))
                expect("JOB_UNAVAILABLE", lambda: reader.get(query))
                result_id = uuid.uuid4()
                with connect(name) as db:
                    with db.transaction():
                        secret = uuid.uuid4()
                        db.execute("INSERT INTO plm.plt_secret_records(secret_record_id,purpose,allowed_consumer,created_by) VALUES (%s,'AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s)", (secret, actor))
                        db.execute("INSERT INTO plm.plt_secret_versions(secret_version_id,secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,%s,1,%s,'{}'::jsonb,'synthetic-only',%s)", (request.secret_version_id, secret, b"x", actor))
                        db.execute("INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) VALUES (%s,%s,%s)", (request.provider_id, request.config_id, actor))
                        db.execute("INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Read','endpoint.synthetic.v1',%s,'cn-beijing','SYNTHETIC',true,false,false,false,%s)", (request.config_id, request.provider_id, secret, actor))
                        db.execute("INSERT INTO plm.ai_provider_probe_results(probe_result_id,ai_provider_id,provider_config_version_id,secret_record_id,secret_version_id,job_id,probe_id,policy_sha256,outcome,attempt_no,fencing_token,observed_at) VALUES (%s,%s,%s,%s,%s,%s,'CHAT_CONNECTIVITY_V1',%s,'SUCCEEDED',1,1,statement_timestamp())", (result_id, request.provider_id, request.config_id, secret, request.secret_version_id, ref.job_id, request.policy_sha256))
                detail = reader.get(query)
                assert (detail.facts.state, detail.owner.result_type, detail.owner.result_id) == (
                    "SUCCEEDED", "AI_PROVIDER_TEST", result_id)
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: reader.get(query))
                print("PASS: PG18 admin authority, immutable pair, success result binding, no missing proof or secret exposure")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
