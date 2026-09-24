from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema

from plm_assistant.modules.platform.infrastructure.database import (
    validate_database_url,
)
from plm_assistant.modules.platform.infrastructure.orm import (
    APPLICATION_SCHEMA,
    Base,
)


config = context.config
if (
    config.config_file_name is not None
    and config.attributes.get("configure_logger", True)
):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> URL:
    injected = config.attributes.get("database_url")
    if injected is not None:
        return validate_database_url(injected)
    configured = config.get_main_option("sqlalchemy.url", "").strip()
    if not configured:
        raise RuntimeError("database URL must be injected by the migration entrypoint")
    return validate_database_url(make_url(configured))


def _include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    if type_ == "schema":
        return name == APPLICATION_SCHEMA
    schema_name = parent_names.get("schema_name")
    return schema_name in (None, APPLICATION_SCHEMA)


def _configuration_options() -> dict[str, object]:
    return {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "include_name": _include_name,
        "version_table": "alembic_version",
        "version_table_schema": APPLICATION_SCHEMA,
        "compare_type": True,
        "compare_server_default": True,
        "transactional_ddl": True,
    }


def run_migrations_offline() -> None:
    url = _database_url()
    offline_url = url.set(password=None)
    context.configure(
        url=offline_url.render_as_string(hide_password=False),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configuration_options(),
    )
    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {APPLICATION_SCHEMA}")
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _database_url(),
        poolclass=NullPool,
        isolation_level="READ COMMITTED",
        connect_args={"application_name": "plm-project-tool-migration"},
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                raise RuntimeError("migrations require PostgreSQL")
            server_version = connection.dialect.server_version_info
            if not server_version or server_version[0] != 18:
                raise RuntimeError("migrations require PostgreSQL 18.x")
            connection.execute(CreateSchema(APPLICATION_SCHEMA, if_not_exists=True))
            connection.commit()
            context.configure(
                connection=connection,
                **_configuration_options(),
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
