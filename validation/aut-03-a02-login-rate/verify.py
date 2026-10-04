"""Disposable PostgreSQL 18 login throttling and migration verification."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimitError, LoginRateLimiter
from plm_assistant.modules.auth.infrastructure import login_rate_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name):
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def denied(limiter, ip, name):
    try:
        limiter.require_slot(client_ip=ip, username=name)
    except LoginRateLimitError as exc:
        assert exc.code == "AUTH_RATE_LIMITED"
    else:
        raise AssertionError("login limit bypassed")


def main():
    suffix = uuid.uuid4().hex[:10]
    names = ["aut03a02_" + suffix + "_" + kind for kind in ("empty", "data")]
    created = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.auth_login_rate_buckets").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0011")
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.auth_login_rate_buckets')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0011")
            with connect(data) as db:
                user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Rate Owner','synthetic rate owner') RETURNING user_id").fetchone()[0]
            command.upgrade(create_migration_config(url(data)), "head")
            engine = create_engine(url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(MigrationContext.configure(connection, opts={
                        "include_schemas": True, "compare_type": True, "compare_server_default": True,
                        "include_name": lambda name, kind, parent: name == "plm" if kind == "schema" else (name != "alembic_version" if kind == "table" else parent.get("schema_name") in (None, "plm")),
                    }), Base.metadata)
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()
            runtime = create_database_runtime(url(data))
            try:
                limiter = LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                           repository=SqlAlchemyLoginRateRepository())
                for _ in range(10):
                    limiter.require_slot(client_ip="127.0.0.1", username=" Alice ")
                denied(limiter, "127.0.0.1", "alice")
                with connect(data) as db:
                    rows = db.execute("SELECT bucket_key,attempt_count FROM plm.auth_login_rate_buckets").fetchall()
                    assert len(rows) == 2 and sorted(row[1] for row in rows) == [10, 11]
                    assert all(len(row[0]) == 32 for row in rows)
                    assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (user,)).fetchone()[0] == 1
                    db.execute("UPDATE plm.auth_login_rate_buckets SET window_started_at=statement_timestamp()-interval '6 minutes' WHERE attempt_count=10")
                limiter.require_slot(client_ip="127.0.0.1", username="alice")
                with connect(data) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_login_rate_buckets WHERE attempt_count=1").fetchone()[0] == 1

                def concurrent(index):
                    try:
                        limiter.require_slot(client_ip="127.0.0.2", username=f"synthetic{index}")
                        return "ALLOW"
                    except LoginRateLimitError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=12) as pool:
                    outcomes = list(pool.map(concurrent, range(40)))
                assert outcomes.count("ALLOW") == 30 and outcomes.count("AUTH_RATE_LIMITED") == 10, outcomes
                with connect(data) as db:
                    count = db.execute("SELECT count(*) FROM plm.auth_login_rate_buckets WHERE attempt_count=30").fetchone()[0]
                    assert count == 1
                    try:
                        db.execute("INSERT INTO plm.auth_login_rate_buckets(bucket_key,window_started_at,last_attempt_at,attempt_count) VALUES (%s,statement_timestamp(),statement_timestamp(),31)", (b"x" * 32,))
                    except psycopg.Error:
                        pass
                    else:
                        raise AssertionError("count constraint bypassed")
                try:
                    command.downgrade(create_migration_config(url(data)), "20260924_0011")
                except RuntimeError as exc:
                    assert "clear login rate buckets" in str(exc)
                else:
                    raise AssertionError("nonempty downgrade accepted")
                with connect(data) as db:
                    db.execute("DELETE FROM plm.auth_login_rate_buckets")
                command.downgrade(create_migration_config(url(data)), "20260924_0011")
                command.upgrade(create_migration_config(url(data)), "head")
                with connect(data) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (user,)).fetchone()[0] == 1
                print("PASS: empty up/down/re-up, populated upgrade, ORM drift=0, limits/concurrency/window/constraints and maintenance downgrade")
            finally:
                runtime.dispose()
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
