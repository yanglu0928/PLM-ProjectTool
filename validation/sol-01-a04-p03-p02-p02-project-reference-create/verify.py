"""Disposable PG18 PROJECT Reference create proof with real private file bytes.

All identities, sessions and source bytes are synthetic. No customer database is used.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateError, ReferenceCreateService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_reference_sources",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
helper = prior.helper


def rejects(action) -> None:
    try:
        action()
    except ReferenceCreateError as error:
        assert error.code in {"RESOURCE_NOT_FOUND", "AUTH_ACCESS_DENIED", "SOURCE_UNAVAILABLE"}, error.code
    else:
        raise AssertionError("unqualified PROJECT Reference was accepted")


def user(db, name: str, token: bytes, csrf: bytes) -> uuid.UUID:
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (name, name.casefold()),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
        "password_hash,algorithm_id,parameter_set) VALUES "
        "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,"
               "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
               (credential, actor))
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
        "statement_timestamp()+interval '2 hours')",
        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
    )
    return actor


def verify(port: int, scratch: Path, on_created=None) -> None:
    token, csrf = b"p" * 32, b"q" * 32
    member_token, member_csrf = b"m" * 32, b"n" * 32

    def on_qualified(*, runtime, request, sources, audit, license_guard,
                     **_unused) -> None:
        global_version = request.document_version_ids[0]
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            manager = user(db, "Project Reference Manager", token, csrf)
            member = user(db, "Project Reference Member", member_token, member_csrf)
            customer = user(db, "Project Reference Customer", b"u" * 32, b"v" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('SOLREFP','solrefp','Reference Project',%s) "
                "RETURNING project_id", (manager,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('SOLREFO','solrefo','Other Project',%s) "
                "RETURNING project_id", (manager,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'REF','ref','Delivery') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in ((manager, "PROJECT_MANAGER"),
                                (member, "IMPLEMENTATION_MEMBER"),
                                (customer, "CUSTOMER_MANAGER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,"
                    "department_id,project_role) VALUES (%s,%s,%s,%s)",
                    (project, actor, department, role),
                )
        storage = LocalFileStorage(scratch / "private-documents")
        content = b"Synthetic PROJECT interview; private test bytes."
        digest = hashlib.sha256(content).digest()
        file_id = uuid.uuid4()
        stage, locator = LocalFileStorage.locators(
            scope="PROJECT", project_id=project, file_object_id=file_id)
        with storage.reserve_staging(stage) as stream:
            stream.write(content)
        storage.publish_verified(stage, locator, expected_sha256=digest,
                                 expected_size=len(content), max_bytes=100_000_000)
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute(
                "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
                "storage_class,storage_locator,original_name_metadata,created_by,"
                "file_state,sha256,size_bytes,detected_mime,available_at) VALUES "
                "(%s,'PROJECT',%s,'PERSISTENT',%s,'project.txt',%s,'AVAILABLE',%s,%s,"
                "'text/plain',statement_timestamp())",
                (file_id, project, locator, manager, digest, len(content)),
            )
            document = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                "title,original_display_name,created_by) VALUES "
                "('PROJECT',%s,'PROJECT_RECORD','Synthetic Interview','project.txt',%s) "
                "RETURNING document_id", (project, manager),
            ).fetchone()[0]
            version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                "source_metadata,created_by) VALUES "
                "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
                "RETURNING document_version_id",
                (document, project, file_id, digest, len(content), Jsonb({}), manager),
            ).fetchone()[0]
            db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                       "effective_version_ref=%s WHERE document_id=%s",
                       (version, version, document))
            evidence = db.execute(
                "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
                "document_version_id,locator_type,locator_payload,content_fingerprint,"
                "display_label,created_by) VALUES "
                "('PROJECT',%s,%s,%s,'DOCUMENT',%s,%s,'Synthetic Interview',%s) "
                "RETURNING evidence_id",
                (project, document, version, Jsonb({"locator_type": "DOCUMENT"}),
                 digest, manager),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                "eligibility_reason='Synthetic review',updated_by=%s,"
                "lock_version=lock_version+1 WHERE evidence_id=%s", (manager, evidence),
            )

        auth = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        service = ReferenceCreateService(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=auth, license_guard=license_guard,
            sources=sources, repository=SqlAlchemyReferenceCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        request = ReferenceSourceRequest(
            token, uuid.uuid4(), "PROJECT", project, (version,), (evidence,),
            "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
        )
        cmd = CreateReferenceSolution(request, csrf, "Project Reference", "p" * 16)
        rejects(lambda: service.create(replace(
            cmd, sources=replace(request, project_id=other_project))))
        rejects(lambda: service.create(replace(
            cmd, sources=replace(request,
                                 document_version_ids=(global_version,)))))
        rejects(lambda: service.create(replace(
            cmd, sources=replace(request, session_token=b"u" * 32),
            csrf_token=b"v" * 32)))
        rejects(lambda: service.create(replace(cmd, csrf_token=b"x" * 32)))
        created = service.create(cmd)
        assert created.scope == "PROJECT" and created.project_id == project
        assert created.deidentification_confirmation_id is None
        assert created.eligibility_state == "REFERENCE_ONLY" and created.version_state == "DRAFT"
        assert service.create(replace(cmd, sources=replace(request, trace_id=uuid.uuid4()))) == created

        member_request = replace(request, session_token=member_token,
                                 trace_id=uuid.uuid4(), evidence_ids=())
        member_cmd = CreateReferenceSolution(
            member_request, member_csrf, "Member Reference", "m" * 16)
        member_created = service.create(member_cmd)
        assert member_created.created_by == member
        if on_created is not None:
            on_created(port=port, scratch=scratch, locator=locator, content=content,
                       runtime=runtime, service=service, sources=sources,
                       audit=audit, license_guard=license_guard, project=project,
                       other_project=other_project, manager=manager, member=member,
                       document_version=version, evidence=evidence,
                       token=token, csrf=csrf,
                       member_token=member_token, member_csrf=member_csrf,
                       documents=_unused["documents"],
                       downloads=_unused["downloads"],
                       parse_results=_unused["parse_results"])
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            expected_count = 2 + (2 if on_created is not None else 0)
            assert db.execute("SELECT count(*) FROM plm.sol_reference_solutions "
                              "WHERE scope='PROJECT' AND project_id=%s",
                              (project,)).fetchone()[0] == expected_count
            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE "
                              "action='SOL_REFERENCE_CREATED' AND target_project_id=%s",
                              (project,)).fetchone()[0] == expected_count
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        rejects(lambda: service.create(cmd))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (manager, project))
        (scratch / "private-documents" / locator).write_bytes(b"X" * len(content))
        rejects(lambda: service.create(replace(cmd, idempotency_key="t" * 16)))
        (scratch / "private-documents" / locator).write_bytes(content)
        assert service.create(cmd) == created

    # The prior fixture migrates the same disposable DB and supplies real source ports.
    prior.verify(port, scratch, on_qualified=on_qualified)
    print("SOL_01_A04_P03_P02_P02_PROJECT_REFERENCE_CREATE_PG_PASS: "
          "PROJECT manager/member real Auth, Document/Evidence/private file, "
          "cross-project, revoke, tamper and replay")


def main(on_created=None) -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-project-ref-pg-"))
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
    port, started = helper.free_port(), False
    try:
        helper.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        helper.run(str(binary / "pg_ctl.exe"), "-D", str(data),
                   "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port, scratch, on_created=on_created)
    finally:
        if started:
            helper.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-project-ref-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
