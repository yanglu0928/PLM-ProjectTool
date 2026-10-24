"""Disposable PG18 proof for immutable Provider probe result Schema 0055."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
PREVIOUS = "20261002_0054"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def migration(name: str):
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    return create_migration_config(url)


def reject(db: psycopg.Connection, statement: str, values: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, values)
    except psycopg.Error as exc:
        assert exc.sqlstate in {"23503", "23505", "23514", "P0001"}, exc.sqlstate
        return
    raise AssertionError("invalid Provider probe result write accepted")


def seed_attempt(db: psycopg.Connection, job: uuid.UUID) -> None:
    db.execute(
        "INSERT INTO plm.job_attempts(job_id,attempt_no,worker_ref,fencing_token,completed_at) "
        "VALUES (%s,1,'synthetic-worker',1,statement_timestamp())", (job,),
    )
    db.execute(
        "INSERT INTO plm.job_leases(job_id,worker_ref,fencing_token,state,lease_expires_at) "
        "VALUES (%s,'synthetic-worker',1,'RELEASED',statement_timestamp()+interval '1 hour')", (job,),
    )


def seed(db: psycopg.Connection, *, second: bool = False) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    label = "second" if second else "first"
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", ("Synthetic Probe " + label, "synthetic probe " + label),
    ).fetchone()[0]
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (actor,),
    ).fetchone()[0]
    secret_version = db.execute(
        "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) "
        "VALUES (%s,1,%s,'{}'::jsonb,'synthetic-only',%s) RETURNING secret_version_id",
        (secret, b"\x01", actor),
    ).fetchone()[0]
    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (secret_version,))
    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (secret_version, secret))
    provider, config = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) VALUES (%s,%s,%s)",
            (provider, config, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) "
            "VALUES (%s,%s,1,'OPENAI_COMPATIBLE',%s,'endpoint.synthetic.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,false,false,%s)",
            (config, provider, "Synthetic Provider " + label, secret, actor),
        )
    job = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,actor_ref,trace_id,payload_refs,idempotency_key,state,attempt_count,max_attempts,fencing_token,completed_at) "
        "VALUES ('ai','AI_PROVIDER_TEST','DEPLOYMENT',%s,%s,'{}'::jsonb,%s,'SUCCEEDED',1,3,1,statement_timestamp()) RETURNING job_id",
        (actor, str(uuid.uuid4()), str(uuid.uuid4())),
    ).fetchone()[0]
    seed_attempt(db, job)
    return provider, config, secret, secret_version, job


INSERT = (
    "INSERT INTO plm.ai_provider_probe_results(ai_provider_id,provider_config_version_id,secret_record_id,secret_version_id,job_id,probe_id,policy_sha256,outcome,failure_code,attempt_no,fencing_token,observed_at) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,statement_timestamp()) RETURNING probe_result_id"
)


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    names = [f"ai01a05p02_{suffix}_{item}" for item in ("empty", "data")]
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            empty_config, data_config = migration(empty), migration(data)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_provider_probe_results')").fetchone()[0] is None
            command.upgrade(empty_config, "head")
            command.check(empty_config)

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                first = seed(db)
                second = seed(db, second=True)
                before = db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0]
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == before == 2
                good = first + ("CHAT_CONNECTIVITY_V1", b"p" * 32, "SUCCEEDED", None, 1, 1)
                result = db.execute(INSERT, good).fetchone()[0]
                assert db.execute("SELECT outcome,policy_sha256 FROM plm.ai_provider_probe_results WHERE probe_result_id=%s", (result,)).fetchone() == ("SUCCEEDED", b"p" * 32)
                failed = second + ("CHAT_CONNECTIVITY_V1", b"f" * 32, "FAILED", "AI_PROVIDER_TIMEOUT", 1, 1)
                db.execute(INSERT, failed)
                assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == 2
                reject(db, INSERT, good)
                for bad in (
                    (second[0], *good[1:]),
                    (first[0], second[1], *good[2:]),
                    (first[0], first[1], second[2], *good[3:]),
                    (first[0], first[1], first[2], second[3], *good[4:]),
                    (*good[:4], uuid.uuid4(), *good[5:]),
                    (*good[:5], "CUSTOM_PROMPT", *good[6:]),
                    (*good[:6], b"short", *good[7:]),
                    (*good[:7], "FAILED", None, *good[9:]),
                    (*good[:7], "SUCCEEDED", "FAILURE", *good[9:]),
                    (*good[:9], 0, 1),
                ):
                    reject(db, INSERT, bad)
                extra_job = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,trace_id,payload_refs,idempotency_key,state,attempt_count,max_attempts,fencing_token,completed_at) "
                    "VALUES ('ai','AI_PROVIDER_TEST','DEPLOYMENT',%s,'{}'::jsonb,%s,'SUCCEEDED',1,3,1,statement_timestamp()) RETURNING job_id",
                    (str(uuid.uuid4()), str(uuid.uuid4())),
                ).fetchone()[0]
                seed_attempt(db, extra_job)
                reject(db, INSERT.replace("statement_timestamp()) RETURNING", "'infinity'::timestamptz) RETURNING"),
                       (*good[:4], extra_job, *good[5:]))
                reject(db, INSERT, (*good[:4], extra_job, *good[5:9], 2, 1))
                reject(db, INSERT, (*good[:4], extra_job, *good[5:10], 2))
                reject(db, "UPDATE plm.ai_provider_probe_results SET outcome='FAILED' WHERE probe_result_id=%s", (result,))
                reject(db, "DELETE FROM plm.ai_provider_probe_results WHERE probe_result_id=%s", (result,))
                reject(db, "TRUNCATE plm.ai_provider_probe_results CASCADE")
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name='ai_provider_probe_results'"
                )}
                assert not columns.intersection({"endpoint_url", "api_key", "plaintext", "request_body", "response_body", "customer_body"})
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "AIProvider probe result history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated probe result downgrade accepted")
            print("PASS: 0055 empty up/down/re-up, populated upgrade, ORM drift=0, composite ownership, immutable history, nonempty downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
