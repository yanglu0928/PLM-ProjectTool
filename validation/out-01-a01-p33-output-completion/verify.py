from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/backend/src"))

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.lease import ClaimedJob
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.output.application.complete_generation import (
    OutputArtifactPublication, OutputGenerationCompletionError,
    OutputGenerationCompletionOwner, OutputValidationEvidence,
)
from plm_assistant.modules.output.infrastructure.complete_generation_repository import (
    SqlAlchemyOutputGenerationCompletionRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database


MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
VALIDATION_CODES = ("FORMAT_CHECK", "STRUCTURE_CHECK", "HASH_CHECK", "CONTENT_CHECK")


class _Transaction:
    def __init__(self, engine):
        self.session = Session(engine, expire_on_commit=False)
        self._committed = False

    def __enter__(self):
        self.session.begin()
        return self

    def commit(self):
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb):
        if not self._committed and self.session.in_transaction():
            self.session.rollback()
        self.session.close()


class _UnitOfWork:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self):
        return _Transaction(self.engine)


class _FailAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def _url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres",
                      host="127.0.0.1", port=port, database=name)


def _seed(dsn: str, *, data: dict) -> None:
    # Only a disposable verifier database is seeded this way. Constraints remain
    # enabled; replication role suppresses unrelated Owner/write triggers while
    # creating cross-module synthetic prerequisites. The tested Artifact,
    # OutputRequest, Execution, DocumentVersion and FileObject references exist.
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("SET session_replication_role='replica'")
        conn.execute(
            "INSERT INTO plm.auth_users "
            "(user_id,username_display,username_normalized,state,deployment_role,"
            "credential_version) VALUES (%(user)s,'synthetic p33 verifier','synthetic-p33',"
            "'DISABLED','NONE',0)", data)
        conn.execute(
            "INSERT INTO plm.prj_projects "
            "(project_id,project_code,project_code_normalized,name,created_by) "
            "VALUES (%(project)s,'SYN-P33','syn-p33','P33 synthetic verifier',%(user)s)",
            data)
        conn.execute(
            "INSERT INTO plm.out_context_snapshots "
            "(context_snapshot_id,project_id,source_version_refs,context_payload,"
            "context_fingerprint,created_by) VALUES "
            "(%(snapshot)s,%(project)s,%(source_refs)s::jsonb,"
            "'{}'::jsonb,%(context_hash)s,%(user)s)", data)
        conn.execute(
            "INSERT INTO plm.job_jobs "
            "(job_id,owner_module,job_type,scope,project_id,actor_ref,trace_id,"
            "payload_refs,idempotency_key,state,attempt_count,max_attempts,fencing_token,"
            "lease_expires_at) VALUES "
            "(%(job)s,'output','OUTPUT_GENERATE','PROJECT',%(project)s,%(user)s,"
            "%(trace_text)s,%(payload)s::jsonb,%(idempotency)s,'RUNNING',2,3,7,%(expires)s)",
            data)
        conn.execute(
            "INSERT INTO plm.job_leases "
            "(lease_id,job_id,worker_ref,fencing_token,state,lease_expires_at) VALUES "
            "(%(lease)s,%(job)s,'p33-verifier-worker',7,'ACTIVE',%(expires)s)", data)
        conn.execute(
            "INSERT INTO plm.job_attempts "
            "(attempt_id,job_id,attempt_no,worker_ref,fencing_token) VALUES "
            "(%(attempt)s,%(job)s,2,'p33-verifier-worker',7)", data)
        conn.execute(
            "INSERT INTO plm.out_output_requests "
            "(output_request_id,project_id,output_type,template_version_ref,source_version_refs,"
            "output_policy_ref,plugin_operation,context_snapshot_id,input_fingerprint,"
            "request_state,job_ref,current_execution_ref,idempotency_key,trace_id,requested_by,lock_version) "
            "VALUES (%(request)s,%(project)s,'DOCX',%(template)s,%(source_refs)s::jsonb,"
            "'synthetic-policy','synthetic.operation',%(snapshot)s,%(context_hash)s,"
            "'GENERATING',%(job)s,%(execution)s,%(request_key)s,%(trace)s,%(user)s,1)", data)
        conn.execute(
            "INSERT INTO plm.plg_executions "
            "(plugin_execution_id,project_id,output_request_id,output_context_snapshot_id,"
            "plugin_installation_id,plugin_package_id,plugin_id_normalized,operation_id,"
            "context_fingerprint,job_id,attempt_no,idempotency_key,execution_state,"
            "result_manifest_ref,result_fingerprint,started_at,completed_at,trace_id) "
            "VALUES (%(execution)s,%(project)s,%(request)s,%(snapshot)s,%(installation)s,"
            "%(package)s,'synthetic.p33','synthetic.operation',%(context_hash)s,%(job)s,2,"
            "'synthetic-p33-execution','SUCCEEDED','synthetic/result-manifest.json',"
            "%(manifest_hash)s,statement_timestamp(),statement_timestamp(),%(trace)s)", data)
        conn.execute(
            "INSERT INTO plm.doc_file_objects "
            "(file_object_id,usage_kind,scope,project_id,storage_class,storage_locator,"
            "original_name_metadata,sha256,size_bytes,detected_mime,file_state,created_by,"
            "available_at) VALUES (%(file)s,'DOCUMENT','PROJECT',%(project)s,'PERSISTENT',"
            "%(locator)s,'synthetic-output.docx',%(content_hash)s,17,%(mime)s,'AVAILABLE',"
            "%(user)s,statement_timestamp())", data)
        conn.execute(
            "INSERT INTO plm.doc_documents "
            "(document_id,scope,project_id,document_category,title,original_display_name,"
            "created_by) VALUES (%(document)s,'PROJECT',%(project)s,'GENERATED_ARTIFACT',"
            "'Synthetic verifier output','synthetic-output.docx',%(user)s)", data)
        conn.execute(
            "INSERT INTO plm.doc_document_versions "
            "(document_version_id,document_id,scope,project_id,version_no,file_object_id,"
            "content_sha256,size_bytes,detected_mime,source_metadata,created_by,"
            "availability_state,integrity_checked_at) VALUES (%(version)s,%(document)s,"
            "'PROJECT',%(project)s,1,%(file)s,%(content_hash)s,17,%(mime)s,'{}'::jsonb,"
            "%(user)s,'AVAILABLE',statement_timestamp())", data)
        conn.execute(
            "UPDATE plm.doc_documents SET latest_version_ref=%(version)s,"
            "effective_version_ref=%(version)s WHERE document_id=%(document)s", data)
        conn.execute("RESET session_replication_role")



def _eligibility_report(dsn: str, data: dict, publication: OutputArtifactPublication,
                        claim: ClaimedJob) -> dict:
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT "
            "EXISTS (SELECT 1 FROM plm.plg_executions WHERE "
            "plugin_execution_id=%s AND output_request_id=%s AND project_id=%s "
            "AND job_id=%s AND attempt_no=%s AND execution_state='SUCCEEDED' "
            "AND result_manifest_ref IS NOT NULL AND result_fingerprint IS NOT NULL), "
            "EXISTS (SELECT 1 FROM plm.doc_file_objects WHERE file_object_id=%s "
            "AND scope='PROJECT' AND project_id=%s AND file_state='AVAILABLE' "
            "AND sha256=%s AND size_bytes=%s AND detected_mime=%s), "
            "EXISTS (SELECT 1 FROM plm.doc_documents WHERE document_id=%s "
            "AND document_category='GENERATED_ARTIFACT' AND scope='PROJECT' "
            "AND project_id=%s AND document_state='ACTIVE'), "
            "EXISTS (SELECT 1 FROM plm.doc_document_versions WHERE "
            "document_version_id=%s AND document_id=%s AND scope='PROJECT' "
            "AND project_id=%s AND file_object_id=%s AND content_sha256=%s "
            "AND size_bytes=%s AND detected_mime=%s AND availability_state='AVAILABLE')",
            (data["execution"],data["request"],data["project"],data["job"],
             claim.attempt_no,data["file"],data["project"],data["content_hash"],
             publication.size_bytes,publication.media_type,data["document"],data["project"],
             data["version"],data["document"],data["project"],data["file"],
             data["content_hash"],publication.size_bytes,publication.media_type),
        ).fetchone()
    return dict(zip(("plugin_execution","file_object","document","document_version"),row))


def _state(dsn: str, data: dict) -> dict:
    with psycopg.connect(dsn) as conn:
        return {
            "request": conn.execute(
                "SELECT request_state FROM plm.out_output_requests WHERE output_request_id=%s",
                (data["request"],)).fetchone()[0],
            "job": conn.execute(
                "SELECT state FROM plm.job_jobs WHERE job_id=%s",
                (data["job"],)).fetchone()[0],
            "lease": conn.execute(
                "SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=7",
                (data["job"],)).fetchone()[0],
            "attempt_completed": conn.execute(
                "SELECT completed_at IS NOT NULL FROM plm.job_attempts "
                "WHERE job_id=%s AND attempt_no=2", (data["job"],)).fetchone()[0],
            "artifacts": conn.execute(
                "SELECT count(*) FROM plm.out_artifacts WHERE output_request_id=%s",
                (data["request"],)).fetchone()[0],
            "validation_results": conn.execute(
                "SELECT count(*) FROM plm.out_artifact_validation_results "
                "WHERE project_id=%s", (data["project"],)).fetchone()[0],
            "audit": conn.execute(
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                "AND action='OUTPUT_GENERATION_SUCCEEDED'", (data["request"],)).fetchone()[0],
        }


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
    database = "plm_outp33_" + args.run_id[-10:]
    admin_dsn = f"postgresql://postgres@127.0.0.1:{args.port}/postgres"
    dsn = f"postgresql://postgres@127.0.0.1:{args.port}/{database}"
    engine = None
    created = False
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{database}"')
        created = True
        upgrade_database(_url(database, args.port))
        engine = create_engine(_url(database, args.port))
        data = {
            "user": uuid.uuid4(), "project": uuid.uuid4(), "snapshot": uuid.uuid4(),
            "job": uuid.uuid4(), "lease": uuid.uuid4(), "attempt": uuid.uuid4(),
            "request": uuid.uuid4(), "template": uuid.uuid4(), "trace": uuid.uuid4(),
            "trace_text": str(uuid.uuid4()), "execution": None,
            "source_refs": json.dumps(["synthetic-source"], separators=(",",":")),
            "installation": uuid.uuid4(), "package": uuid.uuid4(),
            "file": uuid.uuid4(), "document": uuid.uuid4(), "version": uuid.uuid4(),
            "context_hash": bytes.fromhex("12"*32),
            "manifest_hash": bytes.fromhex("34"*32),
            "content_hash": bytes.fromhex("56"*32),
            "mime": MIME, "idempotency": "synthetic-p33-job",
            "request_key": "synthetic-p33-request", "expires": datetime.now(timezone.utc)+timedelta(minutes=10),
        }
        data["execution"] = uuid.uuid5(data["job"], "output-generation:7")
        data["payload"] = json.dumps({
            "output_request_id":str(data["request"]),
            "context_snapshot_id":str(data["snapshot"]),
        }, separators=(",",":"))
        data["locator"] = "generated/" + str(data["file"]) + ".docx"
        _seed(dsn, data=data)
        claim = ClaimedJob(
            data["job"], "OUTPUT_GENERATE", "PROJECT", data["project"],
            {"output_request_id":str(data["request"]),
             "context_snapshot_id":str(data["snapshot"])},
            str(data["trace"]), 7, 2,
        )
        publication = OutputArtifactPublication(
            uuid.uuid4(), data["execution"], data["document"], data["version"], data["file"],
            data["content_hash"], 17, MIME,
            tuple(OutputValidationEvidence(
                code, "PASSED",
                data["content_hash"] if code == "HASH_CHECK" else bytes.fromhex("78"*32),
            ) for code in VALIDATION_CODES),
        )
        uow = _UnitOfWork(engine)
        jobs = SqlAlchemyJobLeaseRepository()
        repository = SqlAlchemyOutputGenerationCompletionRepository()
        owner = OutputGenerationCompletionOwner(
            unit_of_work=uow, jobs=jobs, repository=repository,
            audit=AuditService(SqlAlchemyAuditRepository()), system_actor_id=data["user"],
        )
        try:
            owner.complete(claim, worker_ref="p33-verifier-worker", publication=publication)
        except OutputGenerationCompletionError:
            pass
        else:
            raise AssertionError("synthetic audit failure did not roll back completion")

        after_audit_failure = _state(dsn, data)
        if after_audit_failure != {
            "request":"GENERATING","job":"RUNNING","lease":"ACTIVE",
            "attempt_completed":False,"artifacts":0,"validation_results":0,"audit":0,
        }:
            raise AssertionError("Audit failure did not roll back every PostgreSQL owner")

        wrong_document = OutputArtifactPublication(
            uuid.uuid4(), data["execution"], uuid.uuid4(), data["version"], data["file"],
            data["content_hash"], 17, MIME, publication.validations,
        )
        try:
            owner.complete(claim, worker_ref="p33-verifier-worker",
                           publication=wrong_document)
        except OutputGenerationCompletionError:
            pass
        else:
            raise AssertionError("mismatched Document was accepted")
        if _state(dsn, data) != after_audit_failure:
            raise AssertionError("mismatched reference changed PostgreSQL rows")

        # Use the production AuditService/repository for the successful atomic commit.
        owner = OutputGenerationCompletionOwner(
            unit_of_work=uow, jobs=jobs, repository=repository,
            audit=AuditService(SqlAlchemyAuditRepository()), system_actor_id=data["user"],
        )
        try:
            facts = owner.complete(claim, worker_ref="p33-verifier-worker",
                                   publication=publication)
        except OutputGenerationCompletionError as exc:
            print(json.dumps({
                "status":"DIAGNOSTIC_ONLY",
                "owner_error_code":exc.code,
                "repository_eligibility_predicates":_eligibility_report(
                    dsn, data, publication, claim,
                ),
            },sort_keys=True),file=sys.stderr,flush=True)
            raise
        final = _state(dsn, data)
        if (facts.request_state != "SUCCEEDED" or facts.artifact_state != "AVAILABLE"
                or final != {
                    "request":"SUCCEEDED","job":"SUCCEEDED","lease":"RELEASED",
                    "attempt_completed":True,"artifacts":1,"validation_results":4,"audit":1,
                }):
            raise AssertionError("atomic P33 completion outcome mismatch")
        print(json.dumps({
            "status":"PASS_SCOPE_LIMITED",
            "postgresql":"18.x hosted temporary database",
            "runner_drive":temp.drive,
            "output_request_job_artifact_atomic_success":"PASS",
            "active_lease_fencing":"PASS",
            "project_document_execution_file_binding":"PASS",
            "four_validation_results":"PASS",
            "audit_failure_full_rollback":"PASS",
            "mismatched_document_rejected":"PASS",
            "audit_event_persisted_in_same_transaction":True,
            "files_created":False,"plugin_executed":False,
            "customer_data":False,"production_write_open":False,
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
