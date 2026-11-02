"""Verify PLG-01 package registry migration on isolated PostgreSQL 18 databases."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg import errors, sql
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.platform.infrastructure.migration import (  # noqa: E402
    downgrade_database,
    upgrade_database,
)

HEAD = "20261102_0222"
PARENT = "20261102_0221"
_TABLES = (
    "plg_packages",
    "plg_manifest_operations",
    "plg_manifest_dependencies",
    "plg_package_verifications",
)


def _url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def _dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(
            sql.Identifier(name)))


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(name)))


def _revision(dsn: str) -> str:
    with psycopg.connect(dsn) as conn:
        row = conn.execute("SELECT version_num FROM plm.alembic_version").fetchone()
    if row is None:
        raise AssertionError("database has no Alembic revision")
    return row[0]


def _assert_presence(dsn: str, expected: bool) -> None:
    with psycopg.connect(dsn) as conn:
        found = [
            conn.execute("SELECT to_regclass(%s)", ("plm." + table,)).fetchone()[0]
            for table in _TABLES
        ]
    if (all(found)) is not expected or (not expected and any(found)):
        raise AssertionError(f"PLG-01 table presence mismatch: {found!r}")


def _assert_guards(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        actual = conn.execute(
            "SELECT count(*) FROM pg_trigger "
            "WHERE NOT tgisinternal AND tgname LIKE 'trg_plg_%'"
        ).fetchone()[0]
    if actual != 8:
        raise AssertionError(f"expected eight closed owner/truncate guards, got {actual}")


def _seed_synthetic_history(dsn: str) -> tuple[uuid.UUID, uuid.UUID]:
    package_id, verification_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute(
            "INSERT INTO plm.plg_packages "
            "(plugin_package_id,plugin_id_normalized,plugin_version,package_sha256,"
            "manifest_snapshot,signature,signer_key_ref,compatibility_policy_ref,"
            "package_state,created_at,lock_version) "
            "VALUES (%s,'synthetic.echo','1.0.0',%s,"
            """'{"schema_version":"1"}'::jsonb,%s,'test-key-ref','host-v1',"""
            "'IMPORTED',statement_timestamp(),0)",
            (package_id, b"\x11" * 32, b"synthetic-signature"),
        )
        conn.execute(
            "INSERT INTO plm.plg_manifest_operations "
            "(plugin_package_id,operation_id,output_types,plugin_api_version) "
            "VALUES (%s,'document.render','[\"DOCX\"]'::jsonb,'1')",
            (package_id,),
        )
        conn.execute(
            "INSERT INTO plm.plg_manifest_dependencies "
            "(dependency_id,plugin_package_id,dependency_name,version_spec,dependency_kind) "
            "VALUES (%s,%s,'python-docx','>=1.0,<2','PYTHON')",
            (uuid.uuid4(), package_id),
        )
        conn.execute(
            "INSERT INTO plm.plg_package_verifications "
            "(verification_id,plugin_package_id,verification_state,check_code,summary,"
            "evidence_fingerprint,verified_at) "
            "VALUES (%s,%s,'FAILED','SIGNATURE_CHECK','synthetic invalid signature',%s,"
            "statement_timestamp())",
            (verification_id, package_id, b"\x22" * 32),
        )
        conn.execute("SET session_replication_role = origin")
    return package_id, verification_id


def _assert_immutability_and_closed_owner(dsn: str, package_id: uuid.UUID) -> None:
    with psycopg.connect(dsn) as conn:
        attempts = (
            ("INSERT", "INSERT INTO plm.plg_packages "
             "(plugin_id_normalized,plugin_version,package_sha256,manifest_snapshot,"
             "signature,signer_key_ref,compatibility_policy_ref) "
             "VALUES ('test.other','1.0',decode(repeat('00',32),'hex'),"
             """'{"schema_version":"1"}'::jsonb,'x','key','host-v1')"""),
            ("UPDATE", "UPDATE plm.plg_packages SET plugin_version='2.0' "
             "WHERE plugin_package_id=%s"),
            ("DELETE", "DELETE FROM plm.plg_manifest_operations WHERE plugin_package_id=%s"),
            ("TRUNCATE", "TRUNCATE plm.plg_package_verifications"),
        )
        for operation, statement in attempts:
            try:
                if "%s" in statement:
                    with conn.transaction():
                        conn.execute(statement, (package_id,))
                else:
                    with conn.transaction():
                        conn.execute(statement)
            except errors.RaiseException:
                continue
            raise AssertionError(f"closed package owner allowed {operation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("PLG-01 validation requires a loopback port and numeric run id")
    suffix = args.run_id[-10:]
    empty = f"plg01_{suffix}_empty"
    existing = f"plg01_{suffix}_existing"
    admin = _dsn("postgres", args.port)
    created: list[str] = []
    result = {
        "status": "PASS_LIMITED",
        "head": HEAD,
        "empty_upgrade": "PENDING",
        "empty_downgrade_reupgrade": "PENDING",
        "closed_owner_guards": "PENDING",
        "synthetic_history_retained": "PENDING",
        "history_blocks_downgrade": "PENDING",
        "preexisting_schema_data_retained": "PENDING",
        "customer_data": False,
        "external_calls": 0,
        "production_database": False,
    }
    try:
        _create_database(admin, empty)
        created.append(empty)
        empty_url, empty_dsn = _url(empty, args.port), _dsn(empty, args.port)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != HEAD:
            raise AssertionError("empty upgrade did not reach PLG-01 head")
        _assert_presence(empty_dsn, True)
        _assert_guards(empty_dsn)
        result["empty_upgrade"] = "PASS"
        result["closed_owner_guards"] = "PASS"

        downgrade_database(empty_url, PARENT)
        if _revision(empty_dsn) != PARENT:
            raise AssertionError("empty PLG-01 downgrade did not stop at 0221")
        _assert_presence(empty_dsn, False)
        upgrade_database(empty_url, "head")
        if _revision(empty_dsn) != HEAD:
            raise AssertionError("empty PLG-01 re-upgrade failed")
        _assert_presence(empty_dsn, True)
        result["empty_downgrade_reupgrade"] = "PASS"

        package_id, verification_id = _seed_synthetic_history(empty_dsn)
        _assert_immutability_and_closed_owner(empty_dsn, package_id)
        with psycopg.connect(empty_dsn) as conn:
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM plm.plg_packages),"
                "(SELECT count(*) FROM plm.plg_manifest_operations),"
                "(SELECT count(*) FROM plm.plg_manifest_dependencies),"
                "(SELECT count(*) FROM plm.plg_package_verifications)"
            ).fetchone()
            history = conn.execute(
                "SELECT verification_id FROM plm.plg_package_verifications"
            ).fetchone()[0]
        if counts != (1, 1, 1, 1) or history != verification_id:
            raise AssertionError("synthetic package history changed during guard checks")
        result["synthetic_history_retained"] = "PASS"
        try:
            downgrade_database(empty_url, PARENT)
        except RuntimeError as exc:
            if "history prevents downgrade" not in str(exc):
                raise
        else:
            raise AssertionError("package history did not prevent destructive downgrade")
        if _revision(empty_dsn) != HEAD:
            raise AssertionError("failed downgrade changed the Alembic revision")
        result["history_blocks_downgrade"] = "PASS"

        _create_database(admin, existing)
        created.append(existing)
        existing_url, existing_dsn = _url(existing, args.port), _dsn(existing, args.port)
        upgrade_database(existing_url, PARENT)
        with psycopg.connect(existing_dsn) as conn:
            baseline = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
        upgrade_database(existing_url, "head")
        if _revision(existing_dsn) != HEAD:
            raise AssertionError("existing synthetic database upgrade did not reach PLG-01 head")
        _assert_presence(existing_dsn, True)
        with psycopg.connect(existing_dsn) as conn:
            after = conn.execute(
                "SELECT state,lock_version,changed_at FROM plm.plt_maintenance_state "
                "WHERE state_id=1"
            ).fetchone()
        if baseline is None or after != baseline:
            raise AssertionError("pre-existing synthetic database state changed")
        result["preexisting_schema_data_retained"] = "PASS"
    finally:
        for name in reversed(created):
            _drop_database(admin, name)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
