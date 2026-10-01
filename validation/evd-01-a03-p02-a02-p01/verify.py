"""Isolated PG18 and private-file verification of the Document ParseResult read Port.

All records and bytes are synthetic. Authorization is a checked fake here;
the existing Document download service owns its separate real authorization tests.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.document.application.prepare_download import (
    DownloadError, PrepareDownloadService, VerifiedDownload,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService, FixedSourceProofError,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadQuery, DocumentReadService,
)
from plm_assistant.modules.document.application.read_parse_result import (
    DocumentParseResultReadService, ParseResultReadError,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode, ParsedResult, TextRangePosition,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectActorFacts


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
USER = "poc_admin"


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Snapshots:
    def __init__(self, *, version_id: uuid.UUID, project_id: uuid.UUID,
                 content: bytes) -> None:
        self.version_id, self.project_id, self.content = version_id, project_id, content
        self.allowed = True

    def prepare(self, query: DocumentReadQuery, _document_id: uuid.UUID,
                version_id: uuid.UUID) -> VerifiedDownload:
        if (not self.allowed or query.scope != "PROJECT"
                or query.project_id != self.project_id or version_id != self.version_id):
            raise DownloadError("RESOURCE_NOT_FOUND")
        return VerifiedDownload(version_id, len(self.content), "text/plain",
                                hashlib.sha256(self.content).digest(), io.BytesIO(self.content))


def verify(port: int, scratch: Path) -> None:
    url = URL.create("postgresql+psycopg", username=USER, host="127.0.0.1",
                     port=port, database="postgres")
    command.upgrade(create_migration_config(url), "head")
    source_bytes = b"Synthetic fixed document for Evidence result read."
    source_sha = hashlib.sha256(source_bytes).digest()
    file_id = uuid.uuid4()
    file_root = scratch / "private-documents"
    file_root.mkdir()
    file_storage = LocalFileStorage(file_root)
    with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Evidence Reader','evidence reader') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('EVDR','evdr','Evidence read',%s) RETURNING project_id", (actor,),
        ).fetchone()[0]
        staging, final = LocalFileStorage.locators(
            scope="PROJECT", project_id=project, file_object_id=file_id,
        )
        with file_storage.reserve_staging(staging) as stream:
            stream.write(source_bytes)
        file_storage.publish_verified(
            staging, final, expected_sha256=source_sha,
            expected_size=len(source_bytes), max_bytes=100_000_000,
        )
        document = db.execute(
            "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('PROJECT',%s,'PROJECT_RECORD','Evidence','synthetic.txt',%s) "
            "RETURNING document_id", (project, actor),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,"
            "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
            "VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.txt',%s,"
            "'AVAILABLE',%s,%s,'text/plain',statement_timestamp())",
            (file_id, project, final, actor, source_sha, len(source_bytes)),
        )
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
            "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, project, file_id, source_sha, len(source_bytes), Jsonb({}), actor),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                   "WHERE document_id=%s", (version, version, document))
        job = db.execute(
            "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
            "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
            "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'evd-read-job',3) RETURNING job_id",
            (project, actor, str(uuid.uuid4()),
             Jsonb({"document_id": str(document), "document_version_id": str(version)})),
        ).fetchone()[0]
        record = db.execute(
            "INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
            "parser_profile,parser_version,job_ref,attempt_no) VALUES "
            "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,1) RETURNING parse_record_id",
            (version, project, job),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                   "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s", (record,))
        result_id = uuid.uuid4()
        payload = ParsedResult(
            document_version_id=version, source_sha256=source_sha,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode("synthetic-1", "TEXT_LINE", "Synthetic",
                              TextRangePosition(0, 9, hashlib.sha256(b"Synthetic").hexdigest())),),
        ).canonical_bytes()
        data_root = scratch / "private-results"
        data_root.mkdir()
        storage = LocalParseResultStorage(data_root)
        stored = storage.write_once(scope="PROJECT", project_id=project,
                                    result_ref_id=result_id, content=payload)
        db.execute(
            "INSERT INTO plm.doc_parse_result_refs(parse_result_ref_id,parse_record_id,"
            "storage_locator,result_schema_version,sha256,size_bytes) "
            "VALUES (%s,%s,%s,1,%s,%s)",
            (result_id, record, stored.storage_locator, stored.sha256, stored.size_bytes),
        )
        db.execute("UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                   "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                   "retryable=false,lock_version=2 WHERE parse_record_id=%s",
                   (result_id, stored.sha256, record))
        failed_record = db.execute(
            "INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
            "parser_profile,parser_version,job_ref,attempt_no) VALUES "
            "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,2) RETURNING parse_record_id",
            (version, project, job),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                   "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
                   (failed_record,))
        db.execute("UPDATE plm.doc_parse_records SET parse_state='FAILED',"
                   "completed_at=statement_timestamp(),error_code='PARSER_TEST_FAILED',"
                   "retryable=false,lock_version=2 WHERE parse_record_id=%s",
                   (failed_record,))
        source_locator = json.loads(payload)["nodes"][0]["source_locator"]
        evidence = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
            "document_version_id,source_parse_record_id,locator_type,locator_payload,"
            "content_fingerprint,display_label,created_by) VALUES "
            "('PROJECT',%s,%s,%s,%s,'TEXT_RANGE',%s,%s,'Synthetic node',%s) "
            "RETURNING evidence_id",
            (project, document, version, record, Jsonb(source_locator),
             hashlib.sha256(b"Synthetic").digest(), actor),
        ).fetchone()[0]
        candidate = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
            "document_version_id,locator_type,locator_payload,content_fingerprint,"
            "display_label,created_by) VALUES "
            "('PROJECT',%s,%s,%s,'DOCUMENT',%s,%s,'Candidate',%s) "
            "RETURNING evidence_id",
            (project, document, version, Jsonb({"locator_type": "DOCUMENT"}),
             source_sha, actor),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
            "eligibility_reason='Synthetic review',updated_by=%s,"
            "lock_version=lock_version+1 WHERE evidence_id=%s",
            (actor, evidence),
        )

    runtime = create_database_runtime(url)
    try:
        metadata = SqlAlchemyParseResultReadRepository()
        evidence_sources = SqlAlchemyEvidenceFixedSourceRepository()
        with runtime.unit_of_work() as tx:
            assert evidence_sources.get_for_trace(
                tx, scope="PROJECT", project_id=uuid.uuid4(),
                evidence_id=evidence,
            ) is None
            assert evidence_sources.get_for_trace(
                tx, scope="PROJECT", project_id=project,
                evidence_id=candidate,
            ) is None
            cached = tx.session.get(EvidenceRow, evidence)
            assert cached is not None and cached.lock_version == 1
            with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                 dbname="postgres", autocommit=True) as changer:
                changer.execute(
                    "UPDATE plm.evd_evidence_records SET eligibility_reason='Refreshed',"
                    "updated_by=%s,lock_version=lock_version+1 WHERE evidence_id=%s",
                    (actor, evidence),
                )
            locked_evidence = evidence_sources.get_for_trace(
                tx, scope="PROJECT", project_id=project, evidence_id=evidence,
            )
            assert locked_evidence is not None
            assert locked_evidence.lock_version == 2
            assert locked_evidence.source_parse_record_id == record
            assert locked_evidence.locator == source_locator
            assert locked_evidence.content_fingerprint == hashlib.sha256(b"Synthetic").digest()
            assert cached.lock_version == 2
            with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                 dbname="postgres", autocommit=True) as rival:
                try:
                    rival.execute(
                        "SELECT 1 FROM plm.evd_evidence_records WHERE evidence_id=%s "
                        "FOR UPDATE NOWAIT", (evidence,),
                    )
                except psycopg.Error as error:
                    assert error.sqlstate == "55P03"
                else:
                    raise AssertionError("fixed Evidence row was not held")
        with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                             dbname="postgres", autocommit=True) as changer:
            changer.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='Synthetic revoke',updated_by=%s,"
                "lock_version=lock_version+1 WHERE evidence_id=%s",
                (actor, evidence),
            )
        with runtime.unit_of_work() as tx:
            assert evidence_sources.get_for_trace(
                tx, scope="PROJECT", project_id=project,
                evidence_id=evidence,
            ) is None
        with runtime.unit_of_work() as tx:
            assert metadata.get(tx, scope="PROJECT", project_id=uuid.uuid4(),
                                document_version_id=version, parse_record_id=record) is None
            assert metadata.get(tx, scope="PROJECT", project_id=project,
                                document_version_id=uuid.uuid4(), parse_record_id=record) is None
            assert metadata.get(tx, scope="PROJECT", project_id=project,
                                document_version_id=version, parse_record_id=failed_record) is None
        with runtime.unit_of_work() as tx:
            fixed = metadata.get_for_trace(
                tx, scope="PROJECT", project_id=project,
                document_version_id=version, parse_record_id=record,
            )
            assert fixed is not None and fixed.result_ref_id == result_id
            assert metadata.get_for_trace(
                tx, scope="PROJECT", project_id=uuid.uuid4(),
                document_version_id=version, parse_record_id=record,
            ) is None
            assert metadata.get_for_trace(
                tx, scope="PROJECT", project_id=project,
                document_version_id=version, parse_record_id=failed_record,
            ) is None
            with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                 dbname="postgres", autocommit=True) as rival:
                for table, identity, value in (
                    ("doc_parse_records", "parse_record_id", record),
                    ("doc_parse_result_refs", "parse_result_ref_id", result_id),
                ):
                    try:
                        rival.execute(
                            sql.SQL("SELECT 1 FROM plm.{} WHERE {}=%s FOR UPDATE NOWAIT").format(
                                sql.Identifier(table), sql.Identifier(identity)),
                            (value,),
                        )
                    except psycopg.Error as error:
                        assert error.sqlstate == "55P03", (table, error.sqlstate)
                    else:
                        raise AssertionError(f"fixed {table} row was not held by caller transaction")
        snapshots = Snapshots(version_id=version, project_id=project, content=source_bytes)
        service = DocumentParseResultReadService(
            documents=snapshots, metadata=metadata, storage=storage,
            unit_of_work=runtime.unit_of_work,
        )
        query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", project)
        result = service.read(query, document_id=document,
                              document_version_id=version, parse_record_id=record)
        assert result.content == payload and result.result_ref_id == result_id
        class Session:
            def authenticated_user(self, _tx, *, session_token, now):
                return actor

        class Admin:
            def authorized_admin(self, _tx, *, session_token, now):
                return None

        class Project:
            def actor_facts(self, _tx, *, user_id, project_id, lock=False):
                return ProjectActorFacts("ACTIVE", "PROJECT_MANAGER") if (
                    user_id == actor and project_id == project) else None

        class Guard:
            def require_valid(self, *, trace_id):
                return object()

        class Audit:
            def append(self, _tx, _event):
                return uuid.uuid4()

        reader = DocumentReadService(
            unit_of_work=runtime.unit_of_work, session_access=Session(),
            admin_access=Admin(), project_facts=Project(), license_guard=Guard(),
            repository=SqlAlchemyDocumentReadRepository(),
        )
        downloads = PrepareDownloadService(
            reader=reader, storage=file_storage, unit_of_work=runtime.unit_of_work,
            audit=Audit(),
        )
        actual_results = DocumentParseResultReadService(
            documents=downloads, metadata=metadata, storage=storage,
            unit_of_work=runtime.unit_of_work,
        )
        proof_service = DocumentFixedSourceProofService(
            documents=reader, downloads=downloads,
            parse_metadata=metadata, parse_results=actual_results,
        )
        with runtime.unit_of_work() as tx:
            whole = proof_service.prove(
                tx, query, document_id=document, document_version_id=version,
            )
            parsed_proof = proof_service.prove(
                tx, query, document_id=document, document_version_id=version,
                parse_record_id=record,
            )
            assert whole.facts.content_sha256 == source_sha.hex()
            assert parsed_proof.parse_content == payload
            assert parsed_proof.result_ref_id == result_id
            with psycopg.connect(host="127.0.0.1", port=port, user=USER,
                                 dbname="postgres", autocommit=True) as rival:
                for table, identity, value in (
                    ("doc_documents", "document_id", document),
                    ("doc_document_versions", "document_version_id", version),
                    ("doc_file_objects", "file_object_id", file_id),
                    ("doc_parse_records", "parse_record_id", record),
                    ("doc_parse_result_refs", "parse_result_ref_id", result_id),
                ):
                    try:
                        rival.execute(
                            sql.SQL("SELECT 1 FROM plm.{} WHERE {}=%s FOR UPDATE NOWAIT").format(
                                sql.Identifier(table), sql.Identifier(identity)),
                            (value,),
                        )
                    except psycopg.Error as error:
                        assert error.sqlstate == "55P03", (table, error.sqlstate)
                    else:
                        raise AssertionError(f"fixed {table} row was not held")
        (file_root / final).write_bytes(b"x" * len(source_bytes))
        try:
            with runtime.unit_of_work() as tx:
                proof_service.prove(
                    tx, query, document_id=document, document_version_id=version,
                    parse_record_id=record,
                )
        except FixedSourceProofError as error:
            assert error.code == "FILE_INTEGRITY_MISMATCH"
        else:
            raise AssertionError("tampered physical source accepted")
        (file_root / final).write_bytes(source_bytes)
        locator = json.loads(payload)["nodes"][0]["source_locator"]
        evidence_proof = ParsedNodeEvidenceProofService(results=service).prove(
            query, document_id=document, document_version_id=version,
            parse_record_id=record, locator=locator,
        )
        assert (evidence_proof.node_id == "synthetic-1"
                and evidence_proof.content_fingerprint == hashlib.sha256(b"Synthetic").digest())
        snapshots.allowed = False
        try:
            service.read(query, document_id=document,
                         document_version_id=version, parse_record_id=record)
        except ParseResultReadError as error:
            assert error.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("revoked synthetic reader accepted")
        snapshots.allowed = True
        (data_root / stored.storage_locator).write_bytes(payload[:-1] + b"!")
        try:
            service.read(query, document_id=document,
                         document_version_id=version, parse_record_id=record)
        except ParseResultReadError as error:
            assert error.code == "FILE_INTEGRITY_MISMATCH"
        else:
            raise AssertionError("tampered private result accepted")
        print("PASS: isolated PostgreSQL 18 current ELIGIBLE Evidence lock/scope/"
              "cache refresh/revoke, success/failure ParseRecords, scoped metadata, "
              "caller-transaction Document/Version/File/ParseRecord/ResultRef share locks, "
              "actual private file and result hashes, "
              "exact Evidence node, revoked synthetic reader and tamper rejection")
    finally:
        runtime.dispose()


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-evd-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(PG_SOURCE / name, install / name)
    shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    bin_dir = install / "bin"
    data = scratch / "data"
    log = scratch / "postgres.log"
    port = free_port()
    started = False
    try:
        run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", USER,
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
            "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port, scratch)
    finally:
        if started:
            run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-evd-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
