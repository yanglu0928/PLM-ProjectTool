"""Isolated PG18 empty/data migration and fixed Evidence ParseRecord guard."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import psycopg
from alembic import command
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("evd_pg_setup", ROOT / "validation/evd-01-a03-p02-a02-p01/verify.py")
assert SPEC is not None and SPEC.loader is not None
HELPER = module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
USER = HELPER.USER


def reject(db, statement, args):
    try:
        db.execute(statement, args)
    except psycopg.Error:
        return
    raise AssertionError("invalid Evidence ParseRecord source accepted")


def verify(port):
    url = URL.create("postgresql+psycopg", username=USER, host="127.0.0.1", port=port,
                     database="postgres")
    migration = create_migration_config(url)
    command.upgrade(migration, "20260930_0051")
    # Empty schema up/down and ORM parity.
    command.upgrade(migration, "head")
    command.check(migration)
    command.downgrade(migration, "20260930_0051")
    sha = hashlib.sha256(b"fixed source").digest()
    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                           "VALUES ('Evidence Provenance','evidence provenance') RETURNING user_id").fetchone()[0]
        project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                             "VALUES ('EVPR','evpr','Evidence provenance',%s) RETURNING project_id",
                             (actor,)).fetchone()[0]
        doc = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                         "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                         "'Synthetic','synthetic.txt',%s) RETURNING document_id",
                         (project, actor)).fetchone()[0]
        file_id = db.execute("INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                             "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                             "size_bytes,detected_mime,available_at) VALUES ('PROJECT',%s,'PERSISTENT',"
                             "'synthetic/provenance','synthetic.txt',%s,'AVAILABLE',%s,12,"
                             "'text/plain',statement_timestamp()) RETURNING file_object_id",
                             (project, actor, sha)).fetchone()[0]
        version = db.execute("INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                             "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                             "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,12,"
                             "'text/plain',%s,%s) RETURNING document_version_id",
                             (doc, project, file_id, sha, Jsonb({}), actor)).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                   "WHERE document_id=%s", (version, version, doc))
        insert_old = ("INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
                      "document_version_id,locator_type,locator_payload,content_fingerprint,"
                      "display_label,created_by) VALUES ('PROJECT',%s,%s,%s,%s,%s,%s,%s,%s) "
                      "RETURNING evidence_id")
        old_page = db.execute(insert_old, (project, doc, version, "PAGE",
                                           Jsonb({"locator_type": "PAGE", "page_no": 1}), sha,
                                           "Page 1", actor)).fetchone()[0]
        old_doc = db.execute(insert_old, (project, doc, version, "DOCUMENT",
                                          Jsonb({"locator_type": "DOCUMENT"}), sha,
                                          "Full file", actor)).fetchone()[0]
    command.upgrade(migration, "head")
    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT source_parse_record_id FROM plm.evd_evidence_records "
                          "WHERE evidence_id IN (%s,%s)", (old_page, old_doc)).fetchall() == [(None,), (None,)]
        new_insert = ("INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
                      "document_version_id,locator_type,locator_payload,content_fingerprint,"
                      "display_label,created_by,source_parse_record_id) VALUES "
                      "('PROJECT',%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING evidence_id")
        page = Jsonb({"locator_type": "PAGE", "page_no": 2})
        reject(db, new_insert, (project, doc, version, "PAGE", page, sha, "Page 2", actor, None))
        reject(db, new_insert, (project, doc, version, "DOCUMENT",
                                Jsonb({"locator_type": "DOCUMENT"}), sha, "Full", actor,
                                uuid.uuid4()))
    command.downgrade(migration, "20260930_0051")
    command.upgrade(migration, "head")
    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                         dbname="postgres", autocommit=True) as db:
        job = db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                         "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
                         "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'evd-provenance',3) "
                         "RETURNING job_id", (project, actor, str(uuid.uuid4()),
                                               Jsonb({"document_id": str(doc),
                                                      "document_version_id": str(version)}))).fetchone()[0]
        record = db.execute("INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
                            "parser_profile,parser_version,job_ref,attempt_no) VALUES "
                            "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,1) RETURNING parse_record_id",
                            (version, project, job)).fetchone()[0]
        db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                   "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s", (record,))
        result = uuid.uuid4()
        db.execute("INSERT INTO plm.doc_parse_result_refs(parse_result_ref_id,parse_record_id,"
                   "storage_locator,result_schema_version,sha256,size_bytes) VALUES "
                   "(%s,%s,'synthetic/result',1,%s,12)", (result, record, sha))
        db.execute("UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                   "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                   "retryable=false,lock_version=2 WHERE parse_record_id=%s", (result, sha, record))
        evidence = db.execute(new_insert, (project, doc, version, "PAGE", page,
                                           sha, "Page 2", actor, record)).fetchone()[0]
        reject(db, "UPDATE plm.evd_evidence_records SET source_parse_record_id=NULL "
                   "WHERE evidence_id=%s", (evidence,))
        try:
            command.downgrade(migration, "20260930_0051")
        except Exception as exc:
            assert "Cannot discard fixed Evidence ParseRecord history" in str(exc)
        else:
            raise AssertionError("provenance-bearing history downgrade accepted")
    print("PASS: PG18 empty/data up/down, ORM parity, old-row preservation, new-source guard, downgrade refusal")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-prov-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(HELPER.PG_SOURCE / name, install / name)
    shutil.copy2(HELPER.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(HELPER.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (HELPER.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    bin_dir, data = install / "bin", scratch / "data"
    port, started = HELPER.free_port(), False
    try:
        HELPER.run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", USER,
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        HELPER.run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            HELPER.run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"PostgreSQL remains running; data retained at {scratch}")
        if scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()) and scratch.name.startswith("plm-evd-prov-"):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
