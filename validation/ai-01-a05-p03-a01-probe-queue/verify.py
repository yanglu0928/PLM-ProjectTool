"""Disposable PostgreSQL proof of atomic Provider Test Job/Outbox pairing."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import (
    AIProviderTestEnqueueError, AIProviderTestJobQueue, AIProviderTestJobRequest,
)
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import (
    SqlAlchemyAIProviderTestJobQueueRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def main() -> None:
    name = "ai01a05p03a01_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Queue Owner','synthetic queue owner') RETURNING user_id"
                ).fetchone()[0]
            runtime = create_database_runtime(url)
            try:
                queue = AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository())
                request = AIProviderTestJobRequest(
                    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
                    uuid.uuid4(), actor, uuid.uuid4(), b"p" * 32,
                )
                with runtime.unit_of_work() as tx:
                    assert queue.find(tx, request=request) is None
                    first = queue.enqueue(tx, request=request)
                    assert queue.enqueue(tx, request=request) == first
                    tx.commit()
                with runtime.unit_of_work() as tx:
                    assert queue.find(tx, request=request) == first
                    assert queue.enqueue(tx, request=request) == first
                with connect(name) as db:
                    rows = db.execute(
                        "SELECT j.job_id,e.event_id,j.payload_refs,e.payload_refs,j.state,e.delivery_state "
                        "FROM plm.job_jobs j JOIN plm.job_outbox_events e "
                        "ON e.idempotency_key=j.idempotency_key "
                        "WHERE j.owner_module='ai' AND j.job_type='AI_PROVIDER_TEST'",
                    ).fetchall()
                    assert len(rows) == 1 and rows[0][0:2] == (first.job_id, first.event_id)
                    assert rows[0][4:] == ("PENDING", "PENDING")
                    assert rows[0][3] == dict(rows[0][2], job_id=str(first.job_id))
                    assert set(rows[0][2]) == {"provider_id", "config_id", "secret_version_id", "policy_sha256", "probe_id"}
                    assert not any(word in str(rows[0][2]).lower() for word in ("http", "api_key", "prompt", "customer", "plaintext"))
                with runtime.unit_of_work() as tx:
                    try:
                        queue.enqueue(tx, request=replace(request, config_id=uuid.uuid4()))
                    except AIProviderTestEnqueueError as exc:
                        assert exc.code == "CONFLICT_STATE"
                    else:
                        raise AssertionError("same submission accepted different config")
                rolled = replace(request, submission_id=uuid.uuid4())
                try:
                    with runtime.unit_of_work() as tx:
                        queue.enqueue(tx, request=rolled)
                        raise RuntimeError("synthetic audit outage")
                except RuntimeError:
                    pass
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE idempotency_key=%s", (str(rolled.submission_id),)).fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.job_outbox_events WHERE idempotency_key=%s", (str(rolled.submission_id),)).fetchone()[0] == 0

                orphan = replace(request, submission_id=uuid.uuid4())
                with connect(name) as db:
                    db.execute(
                        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) "
                        "VALUES ('ai','AI_PROVIDER_TEST','DEPLOYMENT',%s,%s,'{}'::jsonb,%s,3)",
                        (actor, str(orphan.trace_id), str(orphan.submission_id)),
                    )
                with runtime.unit_of_work() as tx:
                    try:
                        queue.find(tx, request=orphan)
                    except AIProviderTestEnqueueError as exc:
                        assert exc.code == "CONFLICT_STATE"
                    else:
                        raise AssertionError("one-sided Job accepted as completed pair")

                concurrent = replace(request, submission_id=uuid.uuid4())

                def submit() -> tuple[uuid.UUID, uuid.UUID]:
                    with runtime.unit_of_work() as tx:
                        result = queue.enqueue(tx, request=concurrent)
                        tx.commit()
                        return result.job_id, result.event_id

                with ThreadPoolExecutor(max_workers=2) as pool:
                    values = list(pool.map(lambda _: submit(), range(2)))
                assert values[0] == values[1]
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE idempotency_key=%s", (str(concurrent.submission_id),)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.job_outbox_events WHERE idempotency_key=%s", (str(concurrent.submission_id),)).fetchone()[0] == 1
                print("PASS: Provider Test Job/Outbox atomic pair, replay, mismatch/orphan fail closed, rollback, two-writer concurrency, ref-only payload")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
