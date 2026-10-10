from __future__ import annotations

import unittest
from typing import Any, cast

from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from plm_assistant.modules.platform.infrastructure.database import (
    DatabaseConfigurationError,
    DatabaseEngineOptions,
    DatabaseRuntime,
    UnitOfWorkStateError,
    create_database_runtime,
)


class DatabaseRuntimeTests(unittest.TestCase):
    def test_rejects_non_postgresql_driver(self) -> None:
        with self.assertRaises(DatabaseConfigurationError):
            create_database_runtime("sqlite+pysqlite:///:memory:")

    def test_requires_database_name(self) -> None:
        with self.assertRaises(DatabaseConfigurationError):
            create_database_runtime("postgresql+psycopg://app@localhost")

    def test_rejects_invalid_pool_options(self) -> None:
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseEngineOptions(pool_size=0)
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseEngineOptions(max_overflow=-1)

    def test_safe_url_and_repr_hide_password(self) -> None:
        secret = "must-not-leak"
        runtime = create_database_runtime(
            URL.create(
                "postgresql+psycopg",
                username="app",
                password=secret,
                host="127.0.0.1",
                port=5432,
                database="plm",
            )
        )
        try:
            self.assertNotIn(secret, runtime.safe_url)
            self.assertNotIn(secret, repr(runtime))
            self.assertIn("***", runtime.safe_url)
        finally:
            runtime.dispose()

    def test_unit_of_work_is_not_active_before_enter(self) -> None:
        runtime = create_database_runtime(
            "postgresql+psycopg://app@127.0.0.1:5432/plm"
        )
        try:
            unit_of_work = runtime.unit_of_work()
            with self.assertRaises(UnitOfWorkStateError):
                _ = unit_of_work.session
        finally:
            runtime.dispose()

    def test_readiness_fails_closed_on_sqlalchemy_error(self) -> None:
        class FailingEngine:
            url = URL.create("postgresql+psycopg", database="plm")

            def connect(self) -> None:
                raise SQLAlchemyError("database unavailable")

            def dispose(self) -> None:
                pass

        runtime = DatabaseRuntime(cast(Engine, cast(Any, FailingEngine())))
        self.assertFalse(runtime.is_ready())


if __name__ == "__main__":
    unittest.main()
