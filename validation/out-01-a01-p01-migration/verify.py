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


def _assert_plugin_installation_tables(dsn: str, expected: bool) -> None:
    tables = ("plg_installations", "plg_enabled_operations", "plg_runtime_validations")
    with psycopg.connect(dsn) as conn:
        found = [conn.execute("SELECT to_regclass(%s)", ("plm." + name,)).fetchone()[0]
                 for name in tables]
        owner_closed = conn.execute(
            "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
            "AND tgname IN ('trg_plg_installations__owner_closed', "
            "'trg_plg_enabled_operations__owner_closed', "
            "'trg_plg_runtime_validations__owner_closed')"
        ).fetchone()[0]
    if (all(found)) is not expected or (not expected and any(found)):
        raise AssertionError(f"PluginInstallation table presence mismatch: {found!r}")
    if expected and owner_closed != 3:
        raise AssertionError(f"PluginInstallation write guards are not closed: {owner_closed}")


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
        if _revision(empty_dsn) != "20261104_0225":
            raise AssertionError("empty upgrade did not reach schema head")
        _assert_output_tables(empty_dsn, True)
        _assert_plugin_installation_tables(empty_dsn, True)
        result["empty_database_upgrade"] = "PASS"

        downgrade_database(empty_url, "20261102_0220")
        if _revision(empty_dsn) != "20261102_0220":
            raise AssertionError("owner downgrade did not stop at the Output foundation")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
        if closed != 2 or job_fk != 0: raise AssertionError("0221 downgrade contract mismatch")
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261104_0225": raise AssertionError("owner re-upgrade failed")
        with psycopg.connect(empty_dsn) as conn:
            closed = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname IN ('trg_out_context_snapshots__owner_closed','trg_out_output_requests__owner_closed')").fetchone()[0]
            job_fk = conn.execute("SELECT count(*) FROM pg_constraint WHERE conname='fk_out_output_requests__job'").fetchone()[0]
            immutable = conn.execute("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgname='trg_out_context_snapshots__immutable'").fetchone()[0]
        if closed != 0 or job_fk != 1 or immutable != 1: raise AssertionError("0221 upgrade contract mismatch")
        result["owner_migration_downgrade_reupgrade"] = "PASS"
        downgrade_database(empty_url, "20261026_0210")
        if _revision(empty_dsn) != "20261026_0210": raise AssertionError("P01 downgrade failed")
        _assert_output_tables(empty_dsn, False)
        _assert_plugin_installation_tables(empty_dsn, False)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != "20261104_0225": raise AssertionError("full re-upgrade failed")
        _assert_output_tables(empty_dsn, True)
        _assert_plugin_installation_tables(empty_dsn, True)
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
        upgrade_database(existing_url, "20261103_0224")
        package_id = __import__("uuid").uuid4()
        with psycopg.connect(existing_dsn) as conn:
            conn.execute(
                "INSERT INTO plm.plg_packages "
                "(plugin_package_id,plugin_id_normalized,plugin_version,package_sha256,"
                "manifest_snapshot,signature,signer_key_ref,compatibility_policy_ref,"
                "package_state,verified_at,created_at,lock_version) "
                "VALUES (%s,'synthetic.upgrade','1.0.0',%s,'{\"schema_version\":\"1\"}'::jsonb,"
                "%s,'synthetic-upgrade-key','host.platforms.v1','VERIFIED',"
                "statement_timestamp(),statement_timestamp(),0)",
                (package_id, bytes([0x21]) * 32, bytes([0x31]) * 64),
            )
            conn.execute(
                "INSERT INTO plm.plg_manifest_operations "
                "(plugin_package_id,operation_id,output_types,plugin_api_version) "
                "VALUES (%s,'document.render','[\"DOCX\"]'::jsonb,'1')",
                (package_id,),
            )
        upgrade_database(existing_url, "head")
        if _revision(existing_dsn) != "20261104_0225":
            raise AssertionError("existing database upgrade did not reach schema head")
        _assert_output_tables(existing_dsn, True)
        _assert_plugin_installation_tables(existing_dsn, True)
        with psycopg.connect(existing_dsn) as conn:
            row = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
            retained = conn.execute(
                "SELECT (SELECT count(*) FROM plm.plg_packages WHERE plugin_package_id=%s),"
                "(SELECT count(*) FROM plm.plg_manifest_operations WHERE plugin_package_id=%s)",
                (package_id, package_id),
            ).fetchone()
        if row != existing_maintenance:
            raise AssertionError("pre-existing synthetic data changed during migration")
        if retained != (1, 1):
            raise AssertionError("pre-existing PLG-01 package facts changed during migration")
        result["existing_synthetic_data_upgrade"] = "PASS"
    finally:
        for name in reversed(created):
            _drop_database(admin_dsn, name)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
