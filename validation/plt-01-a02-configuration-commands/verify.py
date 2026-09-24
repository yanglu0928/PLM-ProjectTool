"""Isolated PostgreSQL 18 acceptance for PLT-01-A02."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

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
    CreateConfigurationVersion,
)
from plm_assistant.modules.platform.domain.configuration import (
    ConfigurationValuePolicy,
    ConfigurationValueType,
)
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.configuration_repository import (
    SqlAlchemyConfigurationRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST = "127.0.0.1"
PORT = 55432
USER = "poc_admin"


def _url(db: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=db)


def _conn(db: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=db, autocommit=True)


class AllowAccess:
    def __init__(self) -> None:
        self.allowed = True

    def require_deployment_write(self, uow, actor_id):
        if not self.allowed:
            raise ConfigurationCommandError("RESOURCE_NOT_FOUND")


class TransactionAudit:
    def __init__(self) -> None:
        self.fail = False

    def append(self, uow, *, action, actor_id, configuration_id, version_id, trace_id):
        if self.fail:
            raise RuntimeError("audit unavailable")
        uow.session.execute(
            text("INSERT INTO public.audit_probe(action, configuration_id, version_id) VALUES (:action, :configuration_id, :version_id)"),
            {"action": action, "configuration_id": configuration_id, "version_id": version_id},
        )


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"plt01a02_{token}_{suffix}" for suffix in ("data", "empty", "noninitial")]
    created: list[str] = []
    with _conn("postgres") as admin:
        try:
            for name in names:
                if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
                    raise RuntimeError("validation database name already exists")
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            data, empty, noninitial = names
            command.upgrade(create_migration_config(_url(data)), "20260924_0002")
            with _conn(data) as conn:
                conn.execute("CREATE TABLE public.audit_probe (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, action text NOT NULL, configuration_id uuid NOT NULL, version_id uuid NOT NULL)")
                config_id = conn.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('app.mode') RETURNING system_configuration_id").fetchone()[0]
                actor_id = uuid.uuid4()
                conn.execute(
                    "INSERT INTO plm.plt_configuration_versions(system_configuration_id,version_no,version_state,value_type,value_json,content_fingerprint,created_by) VALUES (%s,1,'ACTIVE','STRING','\"enabled\"'::jsonb,decode(repeat('ab',32),'hex'),%s)",
                    (config_id, actor_id),
                )
            command.upgrade(create_migration_config(_url(data)), "head")
            with _conn(data) as conn:
                assert conn.execute("SELECT schema_version FROM plm.plt_configuration_versions WHERE version_no=1").fetchone()[0] == 1

            engine = create_engine(_url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(
                        MigrationContext.configure(connection, opts={
                            "include_schemas": True,
                            "compare_type": True,
                            "compare_server_default": True,
                            "include_name": lambda name, type_, parent: name == "plm" if type_ == "schema" else (name != "alembic_version" if type_ == "table" else parent.get("schema_name") in (None, "plm")),
                        }), Base.metadata,
                    )
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()

            runtime = create_database_runtime(_url(data))
            access = AllowAccess()
            audit = TransactionAudit()
            service = ConfigurationCommandService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyConfigurationRepository(),
                access=access,
                audit=audit,
                policies={"app.mode": ConfigurationValuePolicy(
                    "app.mode", 1, ConfigurationValueType.STRING,
                    ("enabled", "disabled"),
                )},
            )
            try:
                created_version = service.create_version(CreateConfigurationVersion(
                    config_id, actor_id, 0, 1, "disabled"
                ))
                assert created_version.version_no == 2
                activated = service.activate_version(ActivateConfigurationVersion(
                    config_id, actor_id, 1, 2
                ))
                assert activated.version_id == created_version.version_id
                with _conn(data) as conn:
                    assert conn.execute("SELECT count(*) FROM public.audit_probe").fetchone()[0] == 2
                    assert conn.execute("SELECT active_version_id FROM plm.plt_system_configurations WHERE system_configuration_id=%s", (config_id,)).fetchone()[0] == created_version.version_id
                audit.fail = True
                try:
                    service.create_version(CreateConfigurationVersion(
                        config_id, actor_id, 2, 1, "enabled"
                    ))
                except ConfigurationCommandError as exc:
                    assert exc.code == "SYSTEM_UNAVAILABLE"
                else:
                    raise AssertionError("missing Audit did not fail closed")
                with _conn(data) as conn:
                    assert conn.execute("SELECT count(*) FROM plm.plt_configuration_versions").fetchone()[0] == 2
                    assert conn.execute("SELECT lock_version FROM plm.plt_system_configurations WHERE system_configuration_id=%s", (config_id,)).fetchone()[0] == 2
                audit.fail = False
                access.allowed = False
                try:
                    service.create_version(CreateConfigurationVersion(
                        config_id, actor_id, 2, 1, "enabled"
                    ))
                except ConfigurationCommandError:
                    pass
                else:
                    raise AssertionError("unauthorized write was accepted")
                access.allowed = True

                def race() -> str:
                    try:
                        service.create_version(CreateConfigurationVersion(
                            config_id, actor_id, 2, 1, "enabled"
                        ))
                        return "created"
                    except ConfigurationCommandError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as executor:
                    outcomes = sorted(executor.map(lambda _: race(), range(2)))
                assert outcomes == ["CONFLICT_VERSION", "created"], outcomes
                with _conn(data) as conn:
                    assert conn.execute("SELECT array_agg(version_no ORDER BY version_no) FROM plm.plt_configuration_versions").fetchone()[0] == [1, 2, 3]
                    assert conn.execute("SELECT count(*) FROM public.audit_probe").fetchone()[0] == 3
            finally:
                runtime.dispose()

            command.downgrade(create_migration_config(_url(data)), "20260924_0002")
            with _conn(data) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_configuration_versions").fetchone()[0] == 3
                assert conn.execute("SELECT count(*) FROM public.audit_probe").fetchone()[0] == 3
            command.upgrade(create_migration_config(_url(data)), "head")
            with _conn(data) as conn:
                assert conn.execute("SELECT array_agg(schema_version ORDER BY version_no) FROM plm.plt_configuration_versions").fetchone()[0] == [1, 1, 1]

            command.upgrade(create_migration_config(_url(empty)), "head")
            command.downgrade(create_migration_config(_url(empty)), "20260924_0002")
            command.upgrade(create_migration_config(_url(empty)), "head")
            command.upgrade(create_migration_config(_url(noninitial)), "head")
            with _conn(noninitial) as conn:
                root = conn.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('app.mode') RETURNING system_configuration_id").fetchone()[0]
                conn.execute("INSERT INTO plm.plt_configuration_versions(system_configuration_id,version_no,version_state,schema_version,value_type,value_json,content_fingerprint,created_by) VALUES (%s,1,'ACTIVE',2,'STRING','\"enabled\"'::jsonb,decode(repeat('ab',32),'hex'),uuidv7())", (root,))
            try:
                command.downgrade(create_migration_config(_url(noninitial)), "20260924_0002")
            except RuntimeError as exc:
                assert "noninitial configuration schema versions" in str(exc)
            else:
                raise AssertionError("noninitial schema downgrade was accepted")
            with _conn(noninitial) as conn:
                assert conn.execute("SELECT schema_version FROM plm.plt_configuration_versions").fetchone()[0] == 2
            print("PASS: data/empty up/down, ORM drift=0, version command, activation, same-transaction Audit rollback, authorization, concurrent monotonic versioning, unsafe downgrade refused")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
