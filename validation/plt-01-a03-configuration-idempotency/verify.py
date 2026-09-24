"""Isolated PostgreSQL 18 replay and configuration identity acceptance."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from psycopg import sql
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.application.configuration_commands import (
    ActivateConfigurationVersion,
    ConfigurationCommandError,
    ConfigurationCommandService,
    CreateConfiguration,
    CreateConfigurationVersion,
)
from plm_assistant.modules.platform.domain.configuration import (
    ConfigurationValuePolicy,
    ConfigurationValueType,
)
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.configuration_receipts import (
    SqlAlchemyConfigurationReceiptRepository,
)
from plm_assistant.modules.platform.infrastructure.configuration_repository import (
    SqlAlchemyConfigurationRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST = "127.0.0.1"
PORT = 55432
USER = "poc_admin"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")


def _url(db: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=db)


def _conn(db: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=db, autocommit=True)


class TestAccess:
    def __init__(self) -> None:
        self.allowed = True

    def require_deployment_write(self, uow, actor_id):
        if not self.allowed:
            raise ConfigurationCommandError("RESOURCE_NOT_FOUND")


class TestAudit:
    def __init__(self) -> None:
        self.fail = False

    def append(self, uow, *, action, actor_id, configuration_id, version_id, trace_id):
        if self.fail:
            raise RuntimeError("audit unavailable")
        uow.session.execute(
            text("INSERT INTO public.audit_probe(action, configuration_id, version_id) VALUES (:action, :configuration_id, :version_id)"),
            {"action": action, "configuration_id": configuration_id, "version_id": version_id},
        )


def _service(runtime, access, audit):
    return ConfigurationCommandService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyConfigurationRepository(),
        receipts=SqlAlchemyConfigurationReceiptRepository(),
        access=access,
        audit=audit,
        policies={key: ConfigurationValuePolicy(
            key, 1, ConfigurationValueType.STRING, ("enabled", "disabled")
        ) for key in ("app.mode", "app.other", "app.concurrent", "app.retry")},
    )


def _expect_code(code: str, action) -> None:
    try:
        action()
    except ConfigurationCommandError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"plt01a03_{token}_{suffix}" for suffix in ("data", "empty", "restore")]
    created: list[str] = []
    with _conn("postgres") as admin:
        try:
            for name in names:
                if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
                    raise RuntimeError("validation database name already exists")
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            data, empty, restore = names
            command.upgrade(create_migration_config(_url(data)), "20260924_0003")
            with _conn(data) as conn:
                conn.execute("CREATE TABLE public.audit_probe (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, action text NOT NULL, configuration_id uuid NOT NULL, version_id uuid NULL)")
                conn.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('app.existing')")
            command.upgrade(create_migration_config(_url(data)), "head")
            with _conn(data) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_system_configurations WHERE config_key='app.existing'").fetchone()[0] == 1

            engine = create_engine(_url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(MigrationContext.configure(connection, opts={
                        "include_schemas": True,
                        "compare_type": True,
                        "compare_server_default": True,
                        "include_name": lambda name, type_, parent: name == "plm" if type_ == "schema" else (name != "alembic_version" if type_ == "table" else parent.get("schema_name") in (None, "plm")),
                    }), Base.metadata)
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()

            runtime = create_database_runtime(_url(data))
            access, audit = TestAccess(), TestAudit()
            service = _service(runtime, access, audit)
            actor = uuid.uuid4()
            try:
                key = str(uuid.uuid4())
                command_create = CreateConfiguration("app.mode", actor, key)
                first = service.create_configuration(command_create)
                assert service.create_configuration(command_create) == first
                _expect_code("CONFLICT_IDEMPOTENCY", lambda: service.create_configuration(
                    CreateConfiguration("app.other", actor, key)
                ))
                _expect_code("CONFLICT_DUPLICATE", lambda: service.create_configuration(
                    CreateConfiguration("app.mode", actor, str(uuid.uuid4()))
                ))

                version_key = str(uuid.uuid4())
                version_command = CreateConfigurationVersion(
                    first.configuration_id, actor, 0, 1, "enabled", version_key
                )
                version = service.create_version(version_command)
                assert service.create_version(version_command) == version
                _expect_code("CONFLICT_IDEMPOTENCY", lambda: service.create_version(
                    CreateConfigurationVersion(first.configuration_id, actor, 0, 1, "disabled", version_key)
                ))
                activation_key = str(uuid.uuid4())
                activate_command = ActivateConfigurationVersion(
                    first.configuration_id, actor, 1, 1, activation_key
                )
                activation = service.activate_version(activate_command)
                assert service.activate_version(activate_command) == activation
                assert activation.version_id == version.version_id
                access.allowed = False
                _expect_code("RESOURCE_NOT_FOUND", lambda: service.create_configuration(command_create))
                access.allowed = True

                audit.fail = True
                retry_key = str(uuid.uuid4())
                retry_command = CreateConfiguration("app.retry", actor, retry_key)
                _expect_code("SYSTEM_UNAVAILABLE", lambda: service.create_configuration(retry_command))
                with _conn(data) as conn:
                    assert conn.execute("SELECT count(*) FROM plm.plt_system_configurations WHERE config_key='app.retry'").fetchone()[0] == 0
                    assert conn.execute("SELECT count(*) FROM plm.plt_configuration_command_receipts WHERE operation='CREATE'").fetchone()[0] == 1
                audit.fail = False
                assert service.create_configuration(retry_command).lock_version == 0

                concurrent_key = str(uuid.uuid4())
                concurrent_command = CreateConfiguration("app.concurrent", actor, concurrent_key)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(
                        lambda _: service.create_configuration(concurrent_command), range(2)
                    ))
                assert results[0] == results[1]

                with _conn(data) as conn:
                    assert conn.execute("SELECT count(*) FROM plm.plt_system_configurations WHERE config_key='app.concurrent'").fetchone()[0] == 1
                    assert conn.execute("SELECT count(*) FROM plm.plt_configuration_command_receipts WHERE state='COMPLETED'").fetchone()[0] == 5
                    assert conn.execute("SELECT count(*) FROM public.audit_probe").fetchone()[0] == 5
                    assert conn.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='plm' AND table_name='plt_configuration_command_receipts' AND column_name='idempotency_key'").fetchone()[0] == 0
                    assert conn.execute("SELECT count(*) FROM plm.plt_configuration_command_receipts WHERE key_digest=%s", (key.encode("ascii"),)).fetchone()[0] == 0
                    for statement in (
                        "UPDATE plm.plt_configuration_command_receipts SET result_lock_version=99 WHERE operation='CREATE'",
                        "DELETE FROM plm.plt_configuration_command_receipts WHERE operation='CREATE'",
                    ):
                        try:
                            conn.execute(statement)
                        except psycopg.Error:
                            pass
                        else:
                            raise AssertionError("completed replay receipt was mutable")
                try:
                    command.downgrade(create_migration_config(_url(data)), "20260924_0003")
                except RuntimeError as exc:
                    assert "replay receipts exist" in str(exc)
                else:
                    raise AssertionError("nonempty receipt downgrade was accepted")
                with _conn(data) as conn:
                    assert conn.execute("SELECT count(*) FROM plm.plt_configuration_command_receipts").fetchone()[0] == 5

                # Reconstruct the service to prove that replay state is in PostgreSQL,
                # not retained by a process-local dictionary.
                assert _service(runtime, access, audit).create_configuration(command_create) == first
            finally:
                runtime.dispose()

            with tempfile.TemporaryDirectory(prefix="plt01a03-") as temp:
                dump = str(Path(temp) / "configuration.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True, text=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True, text=True)
            with _conn(restore) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_configuration_command_receipts").fetchone()[0] == 5
                assert conn.execute("SELECT count(*) FROM public.audit_probe").fetchone()[0] == 5

            command.upgrade(create_migration_config(_url(empty)), "head")
            command.downgrade(create_migration_config(_url(empty)), "20260924_0003")
            with _conn(empty) as conn:
                assert conn.execute("SELECT to_regclass('plm.plt_configuration_command_receipts')").fetchone()[0] is None
            command.upgrade(create_migration_config(_url(empty)), "head")
            print("PASS: existing-data/empty migration, ORM drift=0, persistent replay and payload conflict, concurrent single write, authorization, Audit rollback, downgrade guard, dump/restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
