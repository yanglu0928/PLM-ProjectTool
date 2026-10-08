"""Disposable PG18/private-file GLOBAL Reference source composition proof.

All users, Session bytes, source documents, Evidence and License are synthetic.
The Auth/Document/Evidence implementations are real; no customer file or
production database is opened. This is not a human attestation ceremony.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.document.application.prepare_download import PrepareDownloadService
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.application.read_parse_result import DocumentParseResultReadService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.evidence.application.fixed_global_reference_source import EvidenceFixedGlobalReferenceService
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode, ParsedResult, TextRangePosition,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmError,
    ReferenceDeidentificationConfirmService,
)
from plm_assistant.modules.solution.application.prove_reference_deidentification import ReferenceDeidentificationProofService
from plm_assistant.modules.solution.application.reference_source_qualification import (
    ReferenceSourceError, ReferenceSourceQualificationService, ReferenceSourceRequest,
)
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeService, RevokeReferenceDeidentification,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_proof_repository import SqlAlchemyReferenceDeidentificationProofRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_repository import SqlAlchemyReferenceDeidentificationRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_revocation_repository import SqlAlchemyReferenceDeidentificationRevocationRepository
from plm_assistant.modules.solution.infrastructure.reference_document_proof import ReferenceDocumentProofAdapter
from plm_assistant.modules.solution.infrastructure.reference_evidence_proof import ReferenceEvidenceProofAdapter


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "evd_pg_helpers", ROOT / "validation/evd-01-a03-p02-a02-p01/verify.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
TOKEN, CSRF = b"r" * 32, b"c" * 32


class SyntheticLicense:
    def require_valid(self, *, trace_id):
        return object()


def rejects(action) -> None:
    try:
        action()
    except (ReferenceSourceError, ReferenceDeidentificationConfirmError):
        return
    raise AssertionError("unproven GLOBAL source was accepted")


def verify(port: int, scratch: Path, on_qualified=None) -> None:
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, "head")
    command.check(cfg)
    content = b"Synthetic GLOBAL Reference source; no customer data."
    digest = hashlib.sha256(content).digest()
    root = scratch / "private-documents"
    root.mkdir()
    storage = LocalFileStorage(root)
    parse_root = scratch / "private-results"
    parse_root.mkdir()
    parse_storage = LocalParseResultStorage(parse_root)
    file_id = uuid.uuid4()
    stage, locator = LocalFileStorage.locators(
        scope="GLOBAL", project_id=None, file_object_id=file_id)
    with storage.reserve_staging(stage) as stream:
        stream.write(content)
    storage.publish_verified(stage, locator, expected_sha256=digest,
                             expected_size=len(content), max_bytes=100_000_000)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Reference Admin','reference admin') RETURNING user_id"
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
            "password_hash,algorithm_id,parameter_set) VALUES "
            "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
            "RETURNING password_credential_id", (actor,),
        ).fetchone()[0]
        db.execute("UPDATE plm.auth_users SET credential_version=1,"
                   "active_password_credential_id=%s,state='ENABLED',"
                   "deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",
                   (credential, actor))
        db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) "
            "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours')",
            (hashlib.sha256(TOKEN).digest(), hashlib.sha256(CSRF).digest(), actor),
        )
        document = db.execute(
            "INSERT INTO plm.doc_documents(scope,document_category,title,"
            "original_display_name,created_by) VALUES "
            "('GLOBAL','REFERENCE_MATERIAL','Synthetic Reference','synthetic.txt',%s) "
            "RETURNING document_id", (actor,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,storage_class,"
            "storage_locator,original_name_metadata,created_by,file_state,sha256,"
            "size_bytes,detected_mime,available_at) VALUES "
            "(%s,'GLOBAL','PERSISTENT',%s,'synthetic.txt',%s,'AVAILABLE',%s,%s,"
            "'text/plain',statement_timestamp())",
            (file_id, locator, actor, digest, len(content)),
        )
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,version_no,"
            "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
            "created_by) VALUES (%s,'GLOBAL',1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, file_id, digest, len(content), Jsonb({}), actor),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                   "effective_version_ref=%s WHERE document_id=%s",
                   (version, version, document))
        evidence = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,document_id,"
            "document_version_id,locator_type,locator_payload,content_fingerprint,"
            "display_label,created_by) VALUES "
            "('GLOBAL',%s,%s,'DOCUMENT',%s,%s,'Synthetic Reference',%s) "
            "RETURNING evidence_id",
            (document, version, Jsonb({"locator_type": "DOCUMENT"}), digest, actor),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
            "eligibility_reason='Synthetic review',updated_by=%s,"
            "lock_version=lock_version+1 WHERE evidence_id=%s",
            (actor, evidence),
        )
        job = db.execute(
            "INSERT INTO plm.job_jobs(owner_module,job_type,scope,actor_ref,trace_id,"
            "payload_refs,idempotency_key,max_attempts) VALUES "
            "('document','DOCUMENT_PARSE','GLOBAL',%s,%s,%s,'reference-parse-job',3) "
            "RETURNING job_id",
            (actor, str(uuid.uuid4()), Jsonb({
                "document_id": str(document), "document_version_id": str(version),
            })),
        ).fetchone()[0]
        record = db.execute(
            "INSERT INTO plm.doc_parse_records(document_version_id,scope,"
            "parser_profile,parser_version,job_ref,attempt_no) VALUES "
            "(%s,'GLOBAL','PLAIN_TEXT','1',%s,1) RETURNING parse_record_id",
            (version, job),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                   "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
                   (record,))
        payload = ParsedResult(
            document_version_id=version, source_sha256=digest,
            parser_profile="PLAIN_TEXT", parser_version="1",
            nodes=(ParsedNode(
                "reference-line", "TEXT_LINE", "Synthetic",
                TextRangePosition(0, 9, hashlib.sha256(b"Synthetic").hexdigest()),
            ),),
        ).canonical_bytes()
        result_id = uuid.uuid4()
        stored = parse_storage.write_once(
            scope="GLOBAL", project_id=None, result_ref_id=result_id, content=payload)
        db.execute(
            "INSERT INTO plm.doc_parse_result_refs(parse_result_ref_id,parse_record_id,"
            "storage_locator,result_schema_version,sha256,size_bytes) VALUES "
            "(%s,%s,%s,1,%s,%s)",
            (result_id, record, stored.storage_locator, stored.sha256, stored.size_bytes),
        )
        db.execute("UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                   "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                   "retryable=false,lock_version=2 WHERE parse_record_id=%s",
                   (result_id, stored.sha256, record))
        node_locator = json.loads(payload)["nodes"][0]["source_locator"]
        node_evidence = db.execute(
            "INSERT INTO plm.evd_evidence_records(scope,document_id,"
            "document_version_id,source_parse_record_id,locator_type,locator_payload,"
            "content_fingerprint,display_label,created_by) VALUES "
            "('GLOBAL',%s,%s,%s,'TEXT_RANGE',%s,%s,'Synthetic node',%s) "
            "RETURNING evidence_id",
            (document, version, record, Jsonb(node_locator),
             hashlib.sha256(b"Synthetic").digest(), actor),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
            "eligibility_reason='Synthetic node review',updated_by=%s,"
            "lock_version=lock_version+1 WHERE evidence_id=%s",
            (actor, node_evidence),
        )
    runtime = create_database_runtime(url)
    try:
        admin = SqlAlchemyDeploymentReadAccess()
        license_guard = SyntheticLicense()
        audit = AuditService(SqlAlchemyAuditRepository())
        reader = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(), admin_access=admin,
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=license_guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        download = PrepareDownloadService(
            reader=reader, storage=storage, unit_of_work=runtime.unit_of_work,
            audit=audit,
        )
        parse_metadata = SqlAlchemyParseResultReadRepository()
        parse_results = DocumentParseResultReadService(
            documents=download, metadata=parse_metadata,
            storage=parse_storage,
            unit_of_work=runtime.unit_of_work,
        )
        fixed = DocumentFixedSourceProofService(
            documents=reader, downloads=download,
            parse_metadata=parse_metadata, parse_results=parse_results,
        )
        evidence_rows = SqlAlchemyEvidenceFixedSourceRepository()
        evidence_port = ReferenceEvidenceProofAdapter(
            project=EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=SqlAlchemyProjectAuthorizationRepository(),
                evidence=evidence_rows, documents=fixed,
            ),
            global_reference=EvidenceFixedGlobalReferenceService(
                sessions=SqlAlchemyProjectReadAccess(), admins=admin,
                evidence=evidence_rows, documents=fixed,
            ),
        )
        proof = ReferenceDeidentificationProofService(
            admins=admin,
            confirmations=SqlAlchemyReferenceDeidentificationProofRepository(),
        )
        sources = ReferenceSourceQualificationService(
            documents=ReferenceDocumentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed),
            evidence=evidence_port, deidentification=proof,
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        confirm = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
            license_guard=license_guard, sources=sources,
            repository=SqlAlchemyReferenceDeidentificationRepository(),
            receipts=receipts, audit=audit,
        )
        revoke = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
            license_guard=license_guard,
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=receipts, audit=audit,
        )
        request = ReferenceSourceRequest(
            TOKEN, uuid.uuid4(), "GLOBAL", None, (version,), (evidence, node_evidence),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
        )
        with runtime.unit_of_work() as tx:
            baseline = sources.prove_sources(tx, request)
            assert baseline.document_versions[0].content_sha256 == digest
            assert baseline.evidence[0].content_fingerprint == digest
            assert baseline.evidence[1].content_fingerprint == hashlib.sha256(b"Synthetic").digest()
            rejects(lambda: sources.prove_sources(tx, ReferenceSourceRequest(
                TOKEN, request.trace_id, "PROJECT", uuid.uuid4(),
                (version,), (evidence, node_evidence), "PLM", "DEIDENTIFIED",
                {"industry": "synthetic"})))
        rejects(lambda: confirm.confirm(ConfirmReferenceDeidentification(
            request, CSRF, datetime.now(timezone.utc) + timedelta(days=1),
            "I_VERIFIED_DEIDENTIFICATION", "F" * 16,
            expected_source_fingerprint=b"x" * 32,
        )))
        confirmed = confirm.confirm(ConfirmReferenceDeidentification(
            request, CSRF, datetime.now(timezone.utc) + timedelta(days=1),
            "I_VERIFIED_DEIDENTIFICATION", "C" * 16,
            expected_source_fingerprint=baseline.content_fingerprint,
        ))
        assert confirmed.source_fingerprint == baseline.content_fingerprint
        with runtime.unit_of_work() as tx:
            qualified = sources.qualify(tx, request)
            assert qualified.deidentification_confirmation_id == confirmed.confirmation_id
        if on_qualified is not None:
            on_qualified(runtime=runtime, request=request, sources=sources,
                         audit=audit, license_guard=license_guard,
                         qualified=qualified, confirmed=confirmed,
                         documents=reader, downloads=download,
                         parse_results=parse_results)
        (root / locator).write_bytes(b"X" * len(content))
        with runtime.unit_of_work() as tx:
            rejects(lambda: sources.qualify(tx, request))
        (root / locator).write_bytes(content)
        (parse_root / stored.storage_locator).write_bytes(payload[:-1] + b"!")
        with runtime.unit_of_work() as tx:
            rejects(lambda: sources.qualify(tx, request))
        (parse_root / stored.storage_locator).write_bytes(payload)
        with runtime.unit_of_work() as tx:
            assert sources.qualify(tx, request).deidentification_confirmation_id == confirmed.confirmation_id
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',"
                "eligibility_reason='Synthetic withdrawal',updated_by=%s,"
                "lock_version=lock_version+1 WHERE evidence_id=%s",
                (actor, node_evidence),
            )
        with runtime.unit_of_work() as tx:
            rejects(lambda: sources.prove_sources(tx, request))
        revoke.revoke(RevokeReferenceDeidentification(
            confirmed.confirmation_id, TOKEN, CSRF, uuid.uuid4(),
            "ADMIN_REVIEW", "R" * 16,
        ))
        with runtime.unit_of_work() as tx:
            assert proof.prove(
                tx, session_token=TOKEN, trace_id=request.trace_id,
                source_fingerprint=baseline.content_fingerprint,
                source_project_class="PLM", deidentification_class="DEIDENTIFIED",
                applicability={"industry": "synthetic"},
            ) is None
            rejects(lambda: sources.qualify(tx, request))
    finally:
        runtime.dispose()
    print("SOL_01_A04_P02_P03_P03_P03_P02_REAL_SOURCES_PG_PASS: real Auth, "
          "Document/Evidence rows and private source/result files; document "
          "and parsed-node locator proof, scope, byte tamper, Evidence withdrawal "
          "and confirmation revocation denied")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-real-sources-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(helper.PG_SOURCE / name, install / name)
    shutil.copy2(helper.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(helper.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (helper.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = helper.free_port()
    started = False
    try:
        helper.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        helper.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                   "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port, scratch)
    finally:
        if started:
            helper.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-real-sources-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
