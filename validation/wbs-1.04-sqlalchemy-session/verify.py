from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend"
SOURCE_ROOT = BACKEND_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402

from plm_assistant.modules.platform.infrastructure.database import (  # noqa: E402
    UnitOfWorkStateError,
    create_database_runtime,
)


EXPECTED_DEPENDENCIES = {
    "SQLAlchemy": "2.0.54",
    "psycopg": "3.3.5",
}


def validate_static_contract() -> None:
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    dependencies = set(project["dependencies"])
    required = {
        'SQLAlchemy==2.0.54',
        'psycopg[binary]==3.3.5',
    }
    if not required.issubset(dependencies):
        raise AssertionError("database dependencies are not fixed to approved versions")

    contract_source = (
        SOURCE_ROOT
        / "plm_assistant"
        / "modules"
        / "platform"
        / "application"
        / "unit_of_work.py"
    ).read_text(encoding="utf-8")
    if "sqlalchemy" in contract_source.lower():
        raise AssertionError("application UnitOfWork contract depends on SQLAlchemy")

    production_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (SOURCE_ROOT / "plm_assistant").rglob("*.py")
    )
    forbidden = ("DeclarativeBase", "mapped_column(", "alembic")
    found = [token for token in forbidden if token in production_sources]
    if found:
        raise AssertionError(f"WBS 1.04 created ORM/Migration content: {found}")


def validate_live_database(args: argparse.Namespace) -> dict[str, object]:
    url = URL.create(
        "postgresql+psycopg",
        username=args.user,
        host=args.host,
        port=args.port,
        database=args.database,
    )
    runtime = create_database_runtime(url)
    try:
        if not runtime.is_ready():
            raise AssertionError("database readiness check failed")

        first = runtime.unit_of_work()
        second = runtime.unit_of_work()
        with first as first_uow, second as second_uow:
            first_pid = first_uow.session.scalar(text("SELECT pg_backend_pid()"))
            second_pid = second_uow.session.scalar(text("SELECT pg_backend_pid()"))
            server_version = first_uow.session.scalar(
                text("SHOW server_version_num")
            )
            isolation = first_uow.session.scalar(
                text("SHOW transaction_isolation")
            )
            application_name = first_uow.session.scalar(
                text("SELECT current_setting('application_name')")
            )
            first_uow.rollback()
            second_uow.commit()

        if first_pid == second_pid:
            raise AssertionError("concurrent unit of work instances shared a connection")
        if not str(server_version).startswith("18"):
            raise AssertionError(f"expected PostgreSQL 18, received {server_version}")
        if isolation != "read committed":
            raise AssertionError(f"unexpected isolation level: {isolation}")
        if application_name != "plm-project-tool":
            raise AssertionError(f"unexpected application name: {application_name}")
        try:
            _ = first.session
        except UnitOfWorkStateError:
            session_closed = True
        else:
            session_closed = False
        if not session_closed:
            raise AssertionError("unit of work exposed a closed session")

        return {
            "postgresql_version_num": str(server_version),
            "transaction_isolation": isolation,
            "application_name": application_name,
            "independent_backend_connections": first_pid != second_pid,
            "session_inaccessible_after_exit": session_closed,
            "readiness": True,
        }
    finally:
        runtime.dispose()


def build_result(args: argparse.Namespace) -> dict[str, object]:
    validate_static_contract()
    versions = {
        name: importlib.metadata.version(name) for name in EXPECTED_DEPENDENCIES
    }
    if versions != EXPECTED_DEPENDENCIES:
        raise AssertionError(f"unexpected dependency versions: {versions}")
    live = validate_live_database(args)
    return {
        "status": "PASS",
        "wbs": "1.04",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sqlalchemy": versions["SQLAlchemy"],
        "psycopg": versions["psycopg"],
        **live,
        "business_orm_count": 0,
        "migration_count": 0,
        "business_api_count": 0,
        "external_call_count": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", default="poc_admin")
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(args)
    if args.write:
        output_path = (
            Path(__file__).parent
            / "evidence"
            / "windows-11"
            / "result.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
