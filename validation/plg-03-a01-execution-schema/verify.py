from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
import uuid

import psycopg
from sqlalchemy import URL, create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.platform.infrastructure.migration import (
    downgrade_database, upgrade_database,
)


TABLES = (
    "plg_executions",
    "plg_execution_result_files",
    "plg_execution_state_events",
)
REQUIRED_CONSTRAINTS = {
    "fk_plg_executions__output_project",
    "fk_plg_executions__context_project",
    "fk_plg_executions__installation_package",
    "fk_plg_executions__manifest_operation",
    "fk_plg_exec_result_files__file_project",
    "fk_plg_exec_state_events__execution_project",
    "ck_plg_executions__result_shape",
    "ck_plg_exec_result_files__relative_name",
    "ck_plg_exec_state_events__to_state",
}


def admin_dsn(port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/postgres"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    temp = Path(os.environ.get("RUNNER_TEMP", ""))
    if (sys.platform != "win32" or not 1 <= args.port <= 65535
            or not re.fullmatch(r"[0-9]{1,12}", args.run_id)
            or temp.drive.casefold() != "d:"):
        raise ValueError("hosted Windows PostgreSQL and D-drive runner temp required")
    database = "plm_plg03_" + args.run_id[-10:]
    url = URL.create("postgresql+psycopg", username="postgres",
                     host="127.0.0.1", port=args.port, database=database)
    created = False
    engine = None
    try:
        with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{database}"')
        created = True

        upgrade_database(url, "20261104_0230")
        engine = create_engine(url)
        marker_job = uuid.uuid4()
        marker_trace = str(uuid.uuid4())
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO plm.job_jobs "
                "(job_id,owner_module,job_type,scope,project_id,actor_ref,trace_id,"
                "payload_refs,idempotency_key,state,max_attempts) VALUES "
                "(:job,'validation','MIGRATION_SENTINEL','DEPLOYMENT',NULL,NULL,"
                ":trace,'{}'::jsonb,:key,'PENDING',1)"
            ), {"job": marker_job, "trace": marker_trace,
                "key": "plg03-migration-" + args.run_id[-10:]})
        with engine.connect() as conn:
            before_head = conn.execute(
                text("SELECT version_num FROM plm.alembic_version")).scalar_one()
            preexisting = conn.execute(text(
                "SELECT to_regclass('plm.plg_installations') IS NOT NULL "
                "AND to_regclass('plm.out_output_requests') IS NOT NULL")).scalar_one()
            absent_before = all(conn.execute(
                text("SELECT to_regclass(:name) IS NULL"),
                {"name": "plm." + name}).scalar_one() for name in TABLES)
            existing_table_count = conn.execute(text(
                "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='plm'"
            )).scalar_one()
            marker_before = conn.execute(text(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=:job "
                "AND idempotency_key=:key AND trace_id=:trace"
            ), {"job": marker_job, "key": "plg03-migration-" + args.run_id[-10:],
                "trace": marker_trace}).scalar_one()
        if (before_head != "20261104_0230" or not preexisting or not absent_before
                or marker_before != 1):
            raise AssertionError("previous migration head or PLG03 pre-state mismatch")

        upgrade_database(url)
        with engine.connect() as conn:
            head = conn.execute(
                text("SELECT version_num FROM plm.alembic_version")).scalar_one()
            present = all(conn.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": "plm." + name}).scalar_one() for name in TABLES)
            after_table_count = conn.execute(text(
                "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='plm'"
            )).scalar_one()
            constraints = set(conn.execute(text(
                "SELECT conname FROM pg_catalog.pg_constraint c "
                "JOIN pg_catalog.pg_class t ON t.oid=c.conrelid "
                "JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace "
                "WHERE n.nspname='plm' AND t.relname = ANY(:tables)"
            ), {"tables": list(TABLES)}).scalars())
            marker_after = conn.execute(text(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=:job "
                "AND idempotency_key=:key AND trace_id=:trace"
            ), {"job": marker_job, "key": "plg03-migration-" + args.run_id[-10:],
                "trace": marker_trace}).scalar_one()
            triggers = conn.execute(text(
                "SELECT count(*) FROM pg_catalog.pg_trigger tg "
                "JOIN pg_catalog.pg_class t ON t.oid=tg.tgrelid "
                "JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace "
                "WHERE n.nspname='plm' AND NOT tg.tgisinternal "
                "AND t.relname = ANY(:tables)"
            ), {"tables": list(TABLES)}).scalar_one()
        if (head != "20261106_0233" or not present
                or after_table_count != existing_table_count + 5
                or marker_after != marker_before
                or not REQUIRED_CONSTRAINTS.issubset(constraints) or triggers != 6):
            raise AssertionError("PLG03 DDL constraints/guards or additive upgrade mismatch")

        owner_write_closed = True
        try:
            with psycopg.connect(
                f"postgresql://postgres@127.0.0.1:{args.port}/{database}"
            ) as conn:
                conn.execute(
                    "INSERT INTO plm.plg_executions "
                    "(plugin_execution_id,project_id,output_request_id,"
                    "output_context_snapshot_id,plugin_installation_id,"
                    "plugin_package_id,plugin_id_normalized,operation_id,"
                    "context_fingerprint,job_id,attempt_no,idempotency_key,"
                    "trace_id) VALUES "
                    "(gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),"
                    "gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),"
                    "'synthetic.plugin','synthetic.operation',"
                    "decode(repeat('11',32),'hex'),gen_random_uuid(),1,"
                    "'synthetic-owner-closed',gen_random_uuid())"
                )
                owner_write_closed = False
        except psycopg.Error as exc:
            if "owner controlled" not in str(exc):
                raise

        if not owner_write_closed:
            raise AssertionError("PLG03 production write guard was not closed")

        downgrade_database(url, "20261104_0230")
        with engine.connect() as conn:
            absent_after_down = all(conn.execute(
                text("SELECT to_regclass(:name) IS NULL"),
                {"name": "plm." + name}).scalar_one() for name in TABLES)
            down_head = conn.execute(
                text("SELECT version_num FROM plm.alembic_version")).scalar_one()
        if not absent_after_down or down_head != "20261104_0230":
            raise AssertionError("empty downgrade did not restore previous revision")
        upgrade_database(url)
        with engine.connect() as conn:
            reup = all(conn.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": "plm." + name}).scalar_one() for name in TABLES)
            final_head = conn.execute(
                text("SELECT version_num FROM plm.alembic_version")).scalar_one()
        if not reup or final_head != "20261106_0233":
            raise AssertionError("re-upgrade did not restore PLG03 schema")

        print(json.dumps({
            "status": "PASS_SCOPE_LIMITED",
            "wbs": "PLG-03-A01",
            "revision": final_head,
            "upgrade_from_populated_schema_head": True,
            "existing_table_inventory_preserved": True,
            "preexisting_synthetic_job_row_preserved": marker_after == 1,
            "execution_tables": list(TABLES),
            "project_and_immutable_operation_constraints": True,
            "result_file_scope_hash_and_path_constraints": True,
            "state_event_constraints": True,
            "production_write_closed": owner_write_closed,
            "empty_downgrade_reupgrade": True,
            "plugin_executed": False,
            "files_created": False,
            "customer_data": False,
            "external_calls": 0,
            "runner_drive": "D:"
        }, sort_keys=True))
        return 0
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with psycopg.connect(admin_dsn(args.port), autocommit=True) as conn:
                conn.execute(f'DROP DATABASE IF EXISTS "{database}"')


if __name__ == "__main__":
    raise SystemExit(main())
