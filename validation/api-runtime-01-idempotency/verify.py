"""Disposable PostgreSQL proof for generic replay receipts and migration safety."""

from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main() -> None:
    name = "apiidem_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "20260925_0014")
            command.upgrade(config, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts").fetchone()[0] == 0
            command.downgrade(config, "20260925_0014")
            with connect(name) as db:
                assert db.execute("SELECT to_regclass('plm.plt_idempotency_receipts')").fetchone()[0] is None
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Idempotency Owner','synthetic idempotency owner') RETURNING user_id"
                ).fetchone()[0]
                configuration = db.execute(
                    "INSERT INTO plm.plt_system_configurations(config_key,created_by,updated_by) "
                    "VALUES ('app.test',%s,%s) RETURNING system_configuration_id",
                    (actor, actor),
                ).fetchone()[0]
            command.upgrade(config, "head")
            with connect(name) as db:
                assert db.execute("SELECT system_configuration_id FROM plm.plt_system_configurations WHERE config_key='app.test'").fetchone()[0] == configuration
            command.check(config)
            runtime = create_database_runtime(url)
            try:
                receipts = SqlAlchemyIdempotencyReceipts()
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT",
                    key="synthetic-replay-key-1234",
                )
                fingerprint = canonical_payload_fingerprint({"session_id": str(uuid.uuid4())})
                result = IdempotencyResult("V1_AUTH_SESSION", uuid.uuid4(), 200)
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint) is None
                    receipts.complete(tx, scope=scope, result=result)
                    tx.commit()
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=scope, request_fingerprint=fingerprint) == result
                try:
                    with runtime.unit_of_work() as tx:
                        receipts.reserve(tx, scope=scope,
                                         request_fingerprint=canonical_payload_fingerprint({"other": True}))
                except IdempotencyError as exc:
                    assert exc.code == "CONFLICT_IDEMPOTENCY"
                else:
                    raise AssertionError("different payload replay was accepted")
                project_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=uuid.uuid4(), operation="V1_AUTH_LOGOUT",
                    key="synthetic-replay-key-1234",
                )
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=project_scope, request_fingerprint=fingerprint) is None
                    receipts.complete(tx, scope=project_scope, result=result)
                    tx.commit()
                rolled_back = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT",
                    key="synthetic-rollback-key-1234",
                )
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=rolled_back, request_fingerprint=fingerprint) is None
                    # No commit: reservation rolls back with the command.
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=rolled_back, request_fingerprint=fingerprint) is None
                    receipts.complete(tx, scope=rolled_back, result=result)
                    tx.commit()
                pending_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT",
                    key="synthetic-pending-key-1234",
                )
                with runtime.unit_of_work() as tx:
                    assert receipts.reserve(tx, scope=pending_scope, request_fingerprint=fingerprint) is None
                    tx.commit()  # Simulate a broken caller: never replay side effects blindly.
                try:
                    with runtime.unit_of_work() as tx:
                        receipts.reserve(tx, scope=pending_scope, request_fingerprint=fingerprint)
                except IdempotencyError as exc:
                    assert exc.code == "SYSTEM_UNAVAILABLE"
                else:
                    raise AssertionError("unfinished receipt was replayed as success")
                concurrent_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT",
                    key="synthetic-concurrent-key-1234",
                )
                started, second_started, release = threading.Event(), threading.Event(), threading.Event()

                def winner() -> str:
                    with runtime.unit_of_work() as tx:
                        assert receipts.reserve(tx, scope=concurrent_scope, request_fingerprint=fingerprint) is None
                        started.set()
                        assert release.wait(10)
                        receipts.complete(tx, scope=concurrent_scope, result=result)
                        tx.commit()
                    return "created"

                def replay() -> IdempotencyResult | None:
                    assert started.wait(10)
                    second_started.set()
                    with runtime.unit_of_work() as tx:
                        return receipts.reserve(tx, scope=concurrent_scope, request_fingerprint=fingerprint)

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(winner)
                    second = pool.submit(replay)
                    assert second_started.wait(10)
                    time.sleep(0.1)
                    assert not second.done(), "concurrent replay did not wait for first transaction"
                    release.set()
                    assert first.result(timeout=15) == "created"
                    assert second.result(timeout=15) == result
                with connect(name) as db:
                    try:
                        db.execute("UPDATE plm.plt_idempotency_receipts SET result_status=201 WHERE actor_id=%s AND project_id IS NULL AND operation='V1_AUTH_LOGOUT' AND key_digest=%s",
                                   (actor, scope.key_digest))
                    except psycopg.Error:
                        pass
                    else:
                        raise AssertionError("completed receipt mutation was accepted")
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE state='COMPLETED'").fetchone()[0] == 4
                try:
                    command.downgrade(config, "20260925_0014")
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("nonempty receipt downgrade was accepted")
                with connect(name) as db:
                    assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260925_0015"
                print("PASS: empty downgrade, used upgrade, scoped replay/conflict, rollback/pending fail-closed, concurrent single winner, immutable receipt, protected downgrade")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
