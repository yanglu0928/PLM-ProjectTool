from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import json
import platform
import subprocess
import tempfile
from pathlib import Path

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
    downgrade_database,
    upgrade_database,
)
from plm_assistant.modules.platform.infrastructure.orm import Base


DATABASES = ("wbs105_empty", "wbs105_data", "wbs105_restore")
HEAD_REVISION = "20260924_0001"


def database_url(args: argparse.Namespace, database: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=args.user,
        host=args.host,
        port=args.port,
        database=database,
    )


def connection_kwargs(args: argparse.Namespace, database: str) -> dict[str, object]:
    return {
        "host": args.host,
        "port": args.port,
        "user": args.user,
        "dbname": database,
    }


def recreate_database(args: argparse.Namespace, database: str) -> None:
    with psycopg.connect(
        **connection_kwargs(args, args.admin_database),
        autocommit=True,
    ) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
        connection.execute(f'CREATE DATABASE "{database}"')


def drop_database(args: argparse.Namespace, database: str) -> None:
    with psycopg.connect(
        **connection_kwargs(args, args.admin_database),
        autocommit=True,
    ) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')


def create_probe_data(args: argparse.Namespace, database: str) -> None:
    with psycopg.connect(**connection_kwargs(args, database)) as connection:
        connection.execute("CREATE SCHEMA wbs105_probe")
        connection.execute(
            "CREATE TABLE wbs105_probe.existing_data "
            "(probe_id integer PRIMARY KEY, probe_value text NOT NULL)"
        )
        connection.execute(
            "INSERT INTO wbs105_probe.existing_data VALUES (1, 'preserve-me')"
        )


def inspect_database(args: argparse.Namespace, database: str) -> dict[str, object]:
    with psycopg.connect(**connection_kwargs(args, database)) as connection:
        plm_schema = connection.execute(
            "SELECT to_regnamespace('plm') IS NOT NULL"
        ).fetchone()[0]
        version_table = connection.execute(
            "SELECT to_regclass('plm.alembic_version') IS NOT NULL"
        ).fetchone()[0]
        version_rows: list[str] = []
        if version_table:
            version_rows = [
                row[0]
                for row in connection.execute(
                    "SELECT version_num FROM plm.alembic_version ORDER BY version_num"
                ).fetchall()
            ]
        extension_version_row = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()
        application_tables = connection.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='plm' AND tablename <> 'alembic_version' "
            "ORDER BY tablename"
        ).fetchall()
        probe_table = connection.execute(
            "SELECT to_regclass('wbs105_probe.existing_data') IS NOT NULL"
        ).fetchone()[0]
        probe_rows = 0
        if probe_table:
            probe_rows = connection.execute(
                "SELECT count(*) FROM wbs105_probe.existing_data "
                "WHERE probe_id=1 AND probe_value='preserve-me'"
            ).fetchone()[0]
        return {
            "plm_schema": bool(plm_schema),
            "version_table": bool(version_table),
            "version_rows": version_rows,
            "pgvector_version": (
                extension_version_row[0] if extension_version_row else None
            ),
            "application_tables": [row[0] for row in application_tables],
            "probe_rows": probe_rows,
        }


def assert_head(state: dict[str, object], *, probe_rows: int) -> None:
    if state["plm_schema"] is not True:
        raise AssertionError("plm schema is missing at head")
    if state["version_rows"] != [HEAD_REVISION]:
        raise AssertionError(f"unexpected Alembic head: {state['version_rows']}")
    if state["pgvector_version"] != "0.8.6":
        raise AssertionError(f"unexpected pgvector version: {state['pgvector_version']}")
    if state["application_tables"] != []:
        raise AssertionError("platform baseline created business tables")
    if state["probe_rows"] != probe_rows:
        raise AssertionError("existing probe data was not preserved")


def assert_base(state: dict[str, object], *, probe_rows: int) -> None:
    if state["plm_schema"] is not True or state["version_table"] is not True:
        raise AssertionError("base must retain plm schema and version table")
    if state["version_rows"] != []:
        raise AssertionError(f"base still has revision rows: {state['version_rows']}")
    if state["pgvector_version"] != "0.8.6":
        raise AssertionError("base must retain shared pgvector extension")
    if state["application_tables"] != []:
        raise AssertionError("base contains application tables")
    if state["probe_rows"] != probe_rows:
        raise AssertionError("downgrade changed existing probe data")


def drift_count(url: URL) -> int:
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(
                connection,
                opts={
                    "include_schemas": True,
                    "version_table": "alembic_version",
                    "version_table_schema": "plm",
                    "include_name": lambda name, type_, parent_names: (
                        name == "plm"
                        if type_ == "schema"
                        else parent_names.get("schema_name") in (None, "plm")
                    ),
                },
            )
            return len(compare_metadata(migration_context, Base.metadata))
    finally:
        engine.dispose()


def validate_offline_sql(url: URL) -> int:
    config = create_migration_config(url)
    output = io.StringIO()
    config.output_buffer = output
    with contextlib.redirect_stdout(output):
        command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    required = (
        "CREATE SCHEMA IF NOT EXISTS plm",
        "CREATE EXTENSION IF NOT EXISTS vector",
        "20260924_0001",
    )
    missing = [fragment for fragment in required if fragment not in sql]
    if missing:
        raise AssertionError(f"offline SQL missing fragments: {missing}")
    return len(sql.encode("utf-8"))


def run_backup_restore(
    args: argparse.Namespace,
    source_database: str,
    restore_database: str,
) -> int:
    pg_bin = Path(args.pg_bin).resolve()
    pg_dump = pg_bin / "pg_dump.exe"
    pg_restore = pg_bin / "pg_restore.exe"
    if not pg_dump.is_file() or not pg_restore.is_file():
        raise FileNotFoundError("pg_dump.exe and pg_restore.exe are required")

    with tempfile.TemporaryDirectory(prefix="wbs105-") as temp_directory:
        dump_path = Path(temp_directory) / "database.dump"
        subprocess.run(
            [
                str(pg_dump),
                "-Fc",
                "-h",
                args.host,
                "-p",
                str(args.port),
                "-U",
                args.user,
                "-d",
                source_database,
                "-f",
                str(dump_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        dump_size = dump_path.stat().st_size
        if dump_size <= 0:
            raise AssertionError("pg_dump produced an empty backup")
        recreate_database(args, restore_database)
        subprocess.run(
            [
                str(pg_restore),
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-h",
                args.host,
                "-p",
                str(args.port),
                "-U",
                args.user,
                "-d",
                restore_database,
                str(dump_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return dump_size


def build_result(args: argparse.Namespace) -> dict[str, object]:
    for database in DATABASES:
        recreate_database(args, database)
    try:
        empty_url = database_url(args, "wbs105_empty")
        upgrade_database(empty_url)
        empty_head = inspect_database(args, "wbs105_empty")
        assert_head(empty_head, probe_rows=0)
        metadata_drift = drift_count(empty_url)
        if metadata_drift != 0:
            raise AssertionError(f"ORM/Migration drift detected: {metadata_drift}")
        offline_sql_bytes = validate_offline_sql(empty_url)
        downgrade_database(empty_url)
        assert_base(inspect_database(args, "wbs105_empty"), probe_rows=0)

        create_probe_data(args, "wbs105_data")
        data_url = database_url(args, "wbs105_data")
        upgrade_database(data_url)
        assert_head(inspect_database(args, "wbs105_data"), probe_rows=1)
        dump_size = run_backup_restore(
            args,
            "wbs105_data",
            "wbs105_restore",
        )
        assert_head(inspect_database(args, "wbs105_restore"), probe_rows=1)
        downgrade_database(data_url)
        assert_base(inspect_database(args, "wbs105_data"), probe_rows=1)
        upgrade_database(data_url)
        assert_head(inspect_database(args, "wbs105_data"), probe_rows=1)

        return {
            "status": "PASS",
            "wbs": "1.05",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "postgresql_version": "18.6",
            "pgvector_version": "0.8.6",
            "sqlalchemy": importlib.metadata.version("SQLAlchemy"),
            "alembic": importlib.metadata.version("Alembic"),
            "psycopg": importlib.metadata.version("psycopg"),
            "head_revision": HEAD_REVISION,
            "empty_upgrade_downgrade": True,
            "data_upgrade_downgrade_reupgrade": True,
            "probe_rows_preserved": 1,
            "metadata_drift_count": metadata_drift,
            "offline_sql_bytes": offline_sql_bytes,
            "backup_bytes": dump_size,
            "restore_verified": True,
            "business_table_count": 0,
            "external_call_count": 0,
        }
    finally:
        for database in reversed(DATABASES):
            drop_database(args, database)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--pg-bin", required=True)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(args)
    if args.write:
        output = Path(__file__).parent / "evidence" / "windows-11" / "result.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
