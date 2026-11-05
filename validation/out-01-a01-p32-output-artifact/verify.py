from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
import uuid

import psycopg
from psycopg import errors
from sqlalchemy import URL, create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.platform.infrastructure.migration import (
    downgrade_database, upgrade_database,
)


TABLES = ("out_artifacts", "out_artifact_validation_results")
REQUIRED_CONSTRAINTS = {
    "fk_out_artifacts__project",
    "fk_out_artifacts__request_kind_project",
    "fk_out_artifacts__execution_request_project",
    "fk_out_artifacts__generated_document_project",
    "fk_out_artifacts__document_version_content",
    "fk_out_artifacts__file_content_project",
    "fk_out_artifact_validation__artifact_project",
    "ck_out_artifacts__kind_media_type",
    "ck_out_artifacts__state",
    "ck_out_artifacts__validation_summary_codes",
    "ck_out_artifact_validation__code",
}


def _url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def _dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def _must_fail(dsn: str, statement: str, *, params: dict | None = None,
               expected: type[BaseException] | None = None,
               message_part: str | None = None,
               owner_write: bool = False) -> None:
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            if owner_write:
                conn.execute("SET plm.output_artifact_owner_write='on'")
            conn.execute(statement, params or {})
    except Exception as exc:
        if expected is not None and not isinstance(exc, expected):
            raise AssertionError(f"unexpected rejection type {type(exc).__name__}: {exc}") from exc
        if message_part and message_part not in str(exc):
            raise AssertionError(f"unexpected rejection detail: {exc}") from exc
        return
    raise AssertionError(f"expected statement to fail: {statement[:120]}")


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
    database = "plm_outp32_" + args.run_id[-10:]
    admin_dsn = "postgresql://postgres@127.0.0.1:" + str(args.port) + "/postgres"
    url = _url(database, args.port)
    engine = None
    created = False
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{database}"')
        created = True
        upgrade_database(url, "20261105_0231")
        engine = create_engine(url)
        job_id, trace_id = uuid.uuid4(), str(uuid.uuid4())
        idem = "outp32-migration-" + args.run_id[-10:]
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO plm.job_jobs "
                "(job_id,owner_module,job_type,scope,project_id,actor_ref,trace_id,"
                "payload_refs,idempotency_key,state,max_attempts) VALUES "
                "(:job,'validation','OUTP32_SENTINEL','DEPLOYMENT',NULL,NULL,"
                ":trace,'{}'::jsonb,:key,'PENDING',1)"
            ), {"job": job_id, "trace": trace_id, "key": idem})
        with engine.connect() as conn:
            pre_head = conn.execute(text(
                "SELECT version_num FROM plm.alembic_version")).scalar_one()
            pre_state = all(conn.execute(text(
                "SELECT to_regclass(:name) IS NULL"), {"name":"plm."+name}).scalar_one()
                for name in TABLES)
        if pre_head != "20261105_0231" or not pre_state:
            raise AssertionError("P32 pre-upgrade state mismatch")

        upgrade_database(url)
        with engine.connect() as conn:
            head = conn.execute(text(
                "SELECT version_num FROM plm.alembic_version")).scalar_one()
            present = all(conn.execute(text(
                "SELECT to_regclass(:name) IS NOT NULL"), {"name":"plm."+name}).scalar_one()
                for name in TABLES)
            old_job = conn.execute(text(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=:job "
                "AND trace_id=:trace AND idempotency_key=:key"
            ), {"job":job_id,"trace":trace_id,"key":idem}).scalar_one()
            constraints = set(conn.execute(text(
                "SELECT conname FROM pg_catalog.pg_constraint "
                "WHERE connamespace='plm'::regnamespace")).scalars())
            unique_keys = set(conn.execute(text(
                "SELECT conname FROM pg_catalog.pg_constraint WHERE contype='u' "
                "AND connamespace='plm'::regnamespace")).scalars())
            triggers = set(conn.execute(text(
                "SELECT tgname FROM pg_catalog.pg_trigger t "
                "JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid "
                "WHERE NOT t.tgisinternal AND c.relnamespace='plm'::regnamespace"
            )).scalars())
        if head != "20261105_0232" or not present or old_job != 1:
            raise AssertionError("P32 upgrade failed or changed existing synthetic data")
        if not REQUIRED_CONSTRAINTS <= constraints:
            raise AssertionError("P32 required constraints missing")
        required_keys = {
            "uq_out_output_requests__id_project_type",
            "uq_plg_executions__id_request_project",
            "uq_doc_documents__artifact_category_scope",
            "uq_doc_versions__artifact_content",
            "uq_doc_file_objects__artifact_content",
        }
        if not required_keys <= unique_keys:
            raise AssertionError("composite-reference candidate keys missing")
        expected_triggers = {
            "trg_out_artifacts__owner_write", "trg_out_artifacts__no_truncate",
            "trg_out_artifact_validation_results__owner_write",
            "trg_out_artifact_validation_results__no_truncate",
        }
        if not expected_triggers <= triggers:
            raise AssertionError("P32 write protection triggers missing")

        dsn = _dsn(database, args.port)
        artifact_id, project_id = uuid.uuid4(), uuid.uuid4()
        request_id, execution_id = uuid.uuid4(), uuid.uuid4()
        document_id, version_id, file_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        artifact_values = {
            "artifact": artifact_id, "project": project_id, "request": request_id,
            "execution": execution_id, "document": document_id, "version": version_id,
            "file": file_id, "kind": "DOCX",
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "sha": bytes.fromhex("11"*32), "size":1, "state":"VALIDATING",
            "summary": "{}",
        }
        insert_artifact = (
            "INSERT INTO plm.out_artifacts "
            "(output_artifact_id,project_id,output_request_id,plugin_execution_id,"
            "document_id,document_version_id,file_object_id,document_category,scope,"
            "artifact_kind,media_type,artifact_sha256,size_bytes,artifact_state,"
            "validation_summary) VALUES "
            "(%(artifact)s,%(project)s,%(request)s,%(execution)s,%(document)s,"
            "%(version)s,%(file)s,'GENERATED_ARTIFACT','PROJECT',%(kind)s,%(mime)s,"
            "%(sha)s,%(size)s,%(state)s,%(summary)s)"
        )
        _must_fail(dsn, insert_artifact, params=artifact_values,
                   message_part="owner controlled")
        _must_fail(dsn, insert_artifact,
                   params=artifact_values | {"state":"NOT_A_STATE"},
                   expected=errors.CheckViolation, owner_write=True)
        _must_fail(dsn, insert_artifact, params=artifact_values,
                   expected=errors.ForeignKeyViolation, owner_write=True)
        _must_fail(dsn, "TRUNCATE plm.out_artifact_validation_results, plm.out_artifacts",
                   message_part="cannot be truncated")
        _must_fail(dsn, "TRUNCATE plm.out_artifact_validation_results",
                   message_part="cannot be truncated")

        downgrade_database(url, "20261105_0231")
        with engine.connect() as conn:
            down_head = conn.execute(text(
                "SELECT version_num FROM plm.alembic_version")).scalar_one()
            absent = all(conn.execute(text(
                "SELECT to_regclass(:name) IS NULL"), {"name":"plm."+name}).scalar_one()
                for name in TABLES)
            keys_absent = conn.execute(text(
                "SELECT NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname IN "
                "('uq_out_output_requests__id_project_type',"
                "'uq_plg_executions__id_request_project',"
                "'uq_doc_documents__artifact_category_scope',"
                "'uq_doc_versions__artifact_content',"
                "'uq_doc_file_objects__artifact_content'))"
            )).scalar_one()
        if down_head != "20261105_0231" or not absent or not keys_absent:
            raise AssertionError("empty downgrade did not restore previous schema")
        upgrade_database(url)
        with engine.connect() as conn:
            reup = conn.execute(text(
                "SELECT version_num FROM plm.alembic_version")).scalar_one()
            old_job_after = conn.execute(text(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=:job"
            ), {"job":job_id}).scalar_one()
        if reup != "20261105_0232" or old_job_after != 1:
            raise AssertionError("re-upgrade failed or altered existing data")

        # Isolated adversarial trigger fixture: RI is bypassed solely to
        # exercise immutability/history guards, not to claim publishable data.
        fixture_artifact, fixture_project = uuid.uuid4(), uuid.uuid4()
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("SET session_replication_role='replica'")
            conn.execute(
                "INSERT INTO plm.out_artifacts "
                "(output_artifact_id,project_id,output_request_id,plugin_execution_id,"
                "document_id,document_version_id,file_object_id,document_category,scope,"
                "artifact_kind,media_type,artifact_sha256,size_bytes,artifact_state,"
                "validation_summary) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,'GENERATED_ARTIFACT','PROJECT','DOCX',"
                "'application/vnd.openxmlformats-officedocument.wordprocessingml.document',"
                "%s,1,'VALIDATING','{}'::jsonb)",
                (fixture_artifact,fixture_project,uuid.uuid4(),uuid.uuid4(),uuid.uuid4(),
                 uuid.uuid4(),uuid.uuid4(),bytes.fromhex("22"*32)))
            conn.execute("RESET session_replication_role")
            conn.execute("SET plm.output_artifact_owner_write='on'")
            conn.execute(
                "INSERT INTO plm.out_artifact_validation_results "
                "(output_artifact_id,project_id,validation_code,validation_state,"
                "evidence_fingerprint) VALUES (%s,%s,'FORMAT_CHECK','PASSED',%s)",
                (fixture_artifact,fixture_project,bytes.fromhex("33"*32)))
        _must_fail(dsn,
            "UPDATE plm.out_artifact_validation_results SET validation_state='FAILED' "
            "WHERE output_artifact_id=%(artifact)s",
            params={"artifact":fixture_artifact}, message_part="append only")
        _must_fail(dsn,
            "DELETE FROM plm.out_artifact_validation_results "
            "WHERE output_artifact_id=%(artifact)s",
            params={"artifact":fixture_artifact}, message_part="append only")
        _must_fail(dsn,
            "UPDATE plm.out_artifacts SET artifact_sha256=%(sha)s "
            "WHERE output_artifact_id=%(artifact)s",
            params={"sha":bytes.fromhex("44"*32),"artifact":fixture_artifact},
            message_part="append only", owner_write=True)
        _must_fail(dsn,
            "UPDATE plm.out_artifacts SET artifact_state='AVAILABLE',"
            "published_at=statement_timestamp(),lock_version=1 "
            "WHERE output_artifact_id=%(artifact)s",
            params={"artifact":fixture_artifact}, expected=errors.CheckViolation,
            owner_write=True)
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("SET plm.output_artifact_owner_write='on'")
            conn.execute(
                "INSERT INTO plm.out_artifact_validation_results "
                "(output_artifact_id,project_id,validation_code,validation_state) "
                "VALUES (%s,%s,'STRUCTURE_CHECK','PASSED'),"
                "(%s,%s,'HASH_CHECK','PASSED'),(%s,%s,'CONTENT_CHECK','PASSED')",
                (fixture_artifact,fixture_project,fixture_artifact,fixture_project,
                 fixture_artifact,fixture_project))
            conn.execute(
                "UPDATE plm.out_artifacts SET artifact_state='AVAILABLE',"
                "published_at=statement_timestamp(),lock_version=1,"
                "validation_summary='{\"format_code\":\"PASSED\","
                "\"structure_code\":\"PASSED\",\"hash_code\":\"PASSED\","
                "\"content_code\":\"PASSED\"}'::jsonb "
                "WHERE output_artifact_id=%s",
                (fixture_artifact,))
        with engine.connect() as conn:
            available = conn.execute(text(
                "SELECT artifact_state='AVAILABLE' FROM plm.out_artifacts "
                "WHERE output_artifact_id=:artifact"),
                {"artifact":fixture_artifact}).scalar_one()
        if not available:
            raise AssertionError("synthetic fully validated state transition failed")
        try:
            downgrade_database(url, "20261105_0231")
        except RuntimeError as exc:
            if "OutputArtifact history blocks downgrade" not in str(exc):
                raise
        else:
            raise AssertionError("downgrade accepted nonempty artifact history")
        with engine.connect() as conn:
            retained_head = conn.execute(text(
                "SELECT version_num FROM plm.alembic_version")).scalar_one()
            counts = conn.execute(text(
                "SELECT (SELECT count(*) FROM plm.out_artifacts), "
                "(SELECT count(*) FROM plm.out_artifact_validation_results)"
            )).one()
            retained_job = conn.execute(text(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=:job"
            ), {"job":job_id}).scalar_one()
        if retained_head != "20261105_0232" or tuple(counts)!=(1,1) or retained_job!=1:
            raise AssertionError("history refusal changed rows or migration head")

        print(json.dumps({
            "status":"PASS_SCOPE_LIMITED",
            "migration_revision":"20261105_0232",
            "empty_database_upgrade":"PASS",
            "existing_synthetic_data_upgrade":"PASS",
            "empty_database_downgrade_reupgrade":"PASS",
            "history_downgrade_refusal":"PASS",
            "validation_child_append_only":"PASS",
            "artifact_content_immutable":"PASS",
            "owner_write_closed":True,
            "truncate_rejected":True,
            "composite_reference_constraints":"PRESENT",
            "artifact_tables":list(TABLES),
            "preexisting_job_row_preserved":True,
            "runner_drive":temp.drive,
            "production_write_open":False,
            "synthetic_available_transition":"PASS",
            "production_artifact_published":False,
            "files_created":False,
            "plugin_executed":False,
            "customer_data":False,
            "external_calls":0,
        },sort_keys=True))
        return 0
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with psycopg.connect(admin_dsn,autocommit=True) as conn:
                conn.execute(f'DROP DATABASE IF EXISTS "{database}"')


if __name__ == "__main__":
    raise SystemExit(main())
