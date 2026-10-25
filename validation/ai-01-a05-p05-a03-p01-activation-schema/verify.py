"""Disposable PG18 proof of AI Provider activation response Schema 0056."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql


prior = runpy.run_path(str(Path(__file__).parents[1] / "ai-01-a05-p02-probe-result-schema" / "verify.py"))
connect, migration, seed, reject = (prior[name] for name in ("connect", "migration", "seed", "reject"))
PROBE_INSERT = prior["INSERT"]
PREVIOUS = "20261002_0055"

ACTIVATION_INSERT = (
    "INSERT INTO plm.ai_provider_activation_results(activation_result_id,ai_provider_id,"
    "provider_config_version_id,probe_result_id,actor_id,audit_event_id,trace_id,"
    "before_state,result_state,expected_lock_version,lock_version) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    names = [f"ai01a05p05a03_{suffix}_{part}" for part in ("empty", "data")]
    created = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            empty_config, data_config = migration(empty), migration(data)
            command.upgrade(empty_config, PREVIOUS)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_provider_activation_results").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_provider_activation_results')").fetchone()[0] is None
            command.upgrade(empty_config, "head")
            command.check(empty_config)

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                first = seed(db)
                second = seed(db, second=True)
                actor = db.execute("SELECT created_by FROM plm.ai_providers WHERE ai_provider_id=%s", (first[0],)).fetchone()[0]
                probe = db.execute(PROBE_INSERT, first + (
                    "CHAT_CONNECTIVITY_V1", b"p" * 32, "SUCCEEDED", None, 1, 1,
                )).fetchone()[0]
                other_probe = db.execute(PROBE_INSERT, second + (
                    "CHAT_CONNECTIVITY_V1", b"q" * 32, "SUCCEEDED", None, 1, 1,
                )).fetchone()[0]
                before = db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0]
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_provider_probe_results").fetchone()[0] == before == 2
                trace = uuid.uuid4()
                with db.transaction():
                    audit = db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,"
                        "target_owner_module,target_object_type,target_object_id,target_version_id,before_state,after_state) "
                        "VALUES (%s,'DEPLOYMENT','USER',%s,'AI_PROVIDER_ACTIVATED','SUCCESS','ai','AI-01',%s,%s,'CONFIGURED','ACTIVE') "
                        "RETURNING audit_event_id", (trace, actor, first[0], first[1]),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.ai_providers SET provider_state='ACTIVE',lock_version=lock_version+1 WHERE ai_provider_id=%s", (first[0],))
                    values = (uuid.uuid4(), first[0], first[1], probe, actor, audit,
                              trace, "CONFIGURED", "ACTIVE", 0, 1)
                    db.execute(ACTIVATION_INSERT, values)
                assert db.execute("SELECT provider_state,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (first[0],)).fetchone() == ("ACTIVE", 1)
                assert db.execute("SELECT result_state,lock_version FROM plm.ai_provider_activation_results WHERE activation_result_id=%s", (values[0],)).fetchone() == ("ACTIVE", 1)
                reject(db, ACTIVATION_INSERT, (uuid.uuid4(), first[0], first[1], other_probe, *values[4:]))
                reject(db, ACTIVATION_INSERT, (uuid.uuid4(), second[0], second[1], probe, *values[4:]))
                reject(db, ACTIVATION_INSERT, (*values[:5], uuid.uuid4(), *values[6:]))
                reject(db, ACTIVATION_INSERT, (*values[:9], 1, 1))
                reject(db, ACTIVATION_INSERT, (*values[:9], 0, 2))
                reject(db, ACTIVATION_INSERT, (*values[:8], "SUSPENDED", *values[9:]))
                reject(db, "UPDATE plm.ai_provider_activation_results SET result_state='SUSPENDED' WHERE activation_result_id=%s", (values[0],))
                reject(db, "DELETE FROM plm.ai_provider_activation_results WHERE activation_result_id=%s", (values[0],))
                reject(db, "TRUNCATE plm.ai_provider_activation_results CASCADE")
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name='ai_provider_activation_results'"
                )}
                assert not columns.intersection({"api_key", "endpoint_url", "plaintext", "response_body", "customer_body"})
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "AIProvider activation result history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated activation result downgrade accepted")
            print("PASS: 0056 empty up/down/re-up, existing probe upgrade, ORM drift=0, ownership, immutable result, nonempty downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
