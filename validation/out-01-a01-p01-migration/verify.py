"""Verify OUT-01 schema migrations against isolated PostgreSQL 18 databases."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.platform.infrastructure.migration import (  # noqa: E402
    downgrade_database,
    upgrade_database,
)


def _database_url(name: str, port: int) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username="postgres",
        host="127.0.0.1",
        port=port,
        database=name,
    )


def _dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(sql.Identifier(name))
        )


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def _revision(dsn: str) -> str:
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT version_num FROM plm.alembic_version").fetchone()
        if row is None:
            raise AssertionError("database has no Alembic revision")
        return row[0]


def _assert_output_tables(dsn: str, expected: bool) -> None:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT to_regclass('plm.out_context_snapshots'), "
            "to_regclass('plm.out_output_requests')"
        ).fetchone()
    actual = all(rows)
    if actual is not expected:
        raise AssertionError(f"Output table presence mismatch: {rows!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("migration validation requires a loopback port and numeric run id")

    suffix = args.run_id[-10:]
    empty_db = f"plm_out01_{suffix}_empty"
    existing_db = f"plm_out01_{suffix}_existing"
    admin_dsn = _dsn("postgres", args.port)
    created: list[str] = []
    result = {
        "status": "PASS_LIMITED",
        "postgresql_version": None,
        "empty_database_upgrade": "PENDING",
        "owner_migration_downgrade_reupgrade": "PENDING",
        "empty_database_downgrade_reupgrade": "PENDING",
        "existing_synthetic_data_upgrade": "PENDING",
        "customer_data": False,
        "external_api_calls": 0,
        "production_database": False,
    }
    try:
        with psycopg.connect(admin_dsn) as conn:
            result["postgresql_version"] = conn.execute(
                "SELECT current_setting('server_version')"
            ).fetchone()[0]
        _create_database(admin_dsn, empty_db)
        created.append(empty_db)
        empty_url = _database_url(empty_db, args.port)
        empty_dsn = _dsn(empty_db, args.port)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261102_0221":
            raise AssertionError("empty upgrade did not reach OUT-01 migration head")
        _assert_output_tables(empty_dsn, True)
        result["empty_database_upgrade"] = "PASS"

        downgrade_database(empty_url, "20261102_0220")
        if _revision(empty_dsn) != "20261102_0220":
            raise AssertionError("owner downgrade did not stop at the Output foundation")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
        if closed != 2 or job_fk != 0: raise AssertionError("0221 downgrade contract mismatch")
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261102_0221": raise AssertionError("owner re-upgrade failed")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
            immutable = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname='trg_out_context_snapshots__immutable'").fetchone()[0]
        if closed != 0 or job_fk != 1 or immutable != 1: raise AssertionError("0221 upgrade contract mismatch")
        result["owner_migration_downgrade_reupgrade"] = "PASS"
        downgrade_database(empty_url, "20261026_0210")
        if _revision(empty_dsn) != "20261026_0210": raise AssertionError("P01 downgrade failed")
        _assert_output_tables(empty_dsn, False)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261102_0221": raise AssertionError("full re-upgrade failed")
        _assert_output_tables(empty_dsn, True)
        result["empty_database_downgrade_reupgrade"] = "PASS"

        _create_database(admin_dsn, existing_db)
        created.append(existing_db)
        existing_url = _database_url(existing_db, args.port)
        existing_dsn = _dsn(existing_db, args.port)
        upgrade_database(existing_url, "20261026_0210")
        with psycopg.connect(existing_dsn) as conn:
            existing_maintenance = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
        if existing_maintenance is None:
            raise AssertionError("prior migration did not create its expected maintenance singleton")
        upgrade_database(existing_url, "head")
        if _revision(existing_dsn) != "20261102_0221":
            raise AssertionError("existing database upgrade did not reach OUT-01 migration head")
        _assert_output_tables(existing_dsn, True)
        with psycopg.connect(existing_dsn) as conn:
            row = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
        if row != existing_maintenance:
            raise AssertionError("pre-existing synthetic data changed during migration")
        result["existing_synthetic_data_upgrade"] = "PASS"
    finally:
        for name in reversed(created):
            _drop_database(admin_dsn, name)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
