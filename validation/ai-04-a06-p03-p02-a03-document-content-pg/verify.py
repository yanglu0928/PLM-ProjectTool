"""Windows 11/PostgreSQL 18 proof for exact Document AI content ownership.

All database rows and bytes are synthetic.  No provider call or AI Invocation is
created.  A disposable database and private temporary result root are removed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.ai_document_content_owner import (
    AIDocumentContentOwner,
)
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentIdentityQuery,
    AIExecutionContentPlanError,
    AIExecutionContentReadQuery,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionInputRef,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentService,
)
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.parser.application.structured_result import (
    ParsedNode,
    ParsedResult,
    TextRangePosition,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def connect(name: str):
    import psycopg
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


class Guard:
    def require_valid(self, **_kwargs):
        return object()


def seed_result(db, storage, *, actor, project, document, version,
                source_sha, attempt: int, text: str,
                completed_at: datetime):
    job = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
        "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,%s,3) RETURNING job_id",
        (project, actor, str(uuid.uuid4()),
         Jsonb({"document_id": str(document), "document_version_id": str(version)}),
         f"ai-doc-content-{attempt}-{uuid.uuid4().hex}"),
    ).fetchone()[0]
    record = db.execute(
        "INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
        "parser_profile,parser_version,job_ref,attempt_no) VALUES "
        "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,%s) RETURNING parse_record_id",
        (version, project, job, attempt),
    ).fetchone()[0]
    started_at = completed_at - timedelta(seconds=1)
    db.execute(
        "UPDATE plm.doc_parse_records SET parse_state='RUNNING',started_at=%s,"
        "lock_version=1 WHERE parse_record_id=%s", (started_at, record),
    )
    normalized = text.replace("\r\n", "\n")
    payload = ParsedResult(
        document_version_id=version, source_sha256=source_sha,
        parser_profile="PLAIN_TEXT", parser_version="1",
        nodes=(ParsedNode(
            f"synthetic-{attempt}", "TEXT_LINE", text,
            TextRangePosition(
                0, len(normalized),
                hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            ),
        ),),
    ).canonical_bytes()
    result = uuid.uuid4()
    stored = storage.write_once(
        scope="PROJECT", project_id=project, result_ref_id=result,
        content=payload,
    )
    db.execute(
        "INSERT INTO plm.doc_parse_result_refs(parse_result_ref_id,parse_record_id,"
        "storage_locator,result_schema_version,sha256,size_bytes) "
        "VALUES (%s,%s,%s,1,%s,%s)",
        (result, record, stored.storage_locator, stored.sha256, stored.size_bytes),
    )
    db.execute(
        "UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',completed_at=%s,"
        "result_ref=%s,result_sha256=%s,retryable=false,lock_version=2 "
        "WHERE parse_record_id=%s",
        (completed_at, result, stored.sha256, record),
    )
    return record, result, stored


def main() -> None:
    database_name = "ai04a06p03p02a03_" + uuid.uuid4().hex[:8]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database_name,
    )
    scratch = Path(tempfile.mkdtemp(prefix="plm-ai-document-content-"))
    runtime = None
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(database_name)))
    try:
        command.upgrade(create_migration_config(url), "head")
        result_root = scratch / "results"
        result_root.mkdir()
        storage = LocalParseResultStorage(result_root)
        with connect(database_name) as db:
            actor = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('Document AI Worker','document ai worker') RETURNING user_id",
            ).fetchone()[0]
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('AIDOCPG1','aidocpg1','Document AI content',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'DEL','del','Delivery') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            member = db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') "
                "RETURNING project_member_id", (project, actor, department),
            ).fetchone()[0]
            source_bytes = "合成项目需求正文".encode("utf-8")
            source_sha = hashlib.sha256(source_bytes).digest()
            document = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES "
                "('PROJECT',%s,'PROJECT_RECORD','Synthetic AI source','synthetic.txt',%s) "
                "RETURNING document_id", (project, actor),
            ).fetchone()[0]
            file_id = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
                "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
                "detected_mime,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,"
                "'synthetic.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp())",
                (file_id, project, f"projects/{project.hex}/synthetic.txt", actor,
                 source_sha, len(source_bytes)),
            )
            version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
                "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by) "
                "VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
                "RETURNING document_version_id",
                (document, project, file_id, source_sha, len(source_bytes),
                 Jsonb({"synthetic": True}), actor),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                "WHERE document_id=%s", (version, version, document),
            )
            first_record, first_result, first_stored = seed_result(
                db, storage, actor=actor, project=project, document=document,
                version=version, source_sha=source_sha, attempt=1,
                text="第一版需求\r\n固定正文",
                completed_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            )

        runtime = create_database_runtime(url)
        projects = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        service = DocumentAIContentService(
            repository=SqlAlchemyDocumentAIContentRepository(), storage=storage,
            projects=projects, license_guard=Guard(),
        )
        owner = AIDocumentContentOwner(service)
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            document, version, project,
        )
        plan_id = uuid.uuid4()
        identity_query = AIExecutionContentIdentityQuery(
            plan_id, project, actor, uuid.uuid4(), "gap.analysis.v1",
            "minimum.document.text.v1", "document.parse.fixed.v1",
        )
        with runtime.unit_of_work() as tx:
            frozen = owner.resolve_identity(
                tx, query=identity_query, input_ref=input_ref)
        assert frozen.content_revision_id == first_record
        assert frozen.content_object_id == first_result

        with connect(database_name) as db:
            second_record, second_result, _ = seed_result(
                db, storage, actor=actor, project=project, document=document,
                version=version, source_sha=source_sha, attempt=2,
                text="第二版较新解析正文",
                completed_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        read_query = AIExecutionContentReadQuery(
            plan_id, uuid.uuid4(), project, uuid.uuid4(), actor, uuid.uuid4(),
            uuid.uuid4(), "gap.analysis.v1", "minimum.document.text.v1",
        )
        with runtime.unit_of_work() as tx:
            old_projection = owner.read_exact(
                tx, query=read_query, source=frozen)
            current = owner.resolve_identity(
                tx, query=identity_query, input_ref=input_ref)
        old_payload = json.loads(old_projection.content_utf8)
        assert old_payload["nodes"][0]["text"] == "第一版需求\n固定正文"
        assert current.content_revision_id == second_record
        assert current.content_object_id == second_result
        assert current.content_revision_id != frozen.content_revision_id

        with connect(database_name) as db:
            db.execute(
                "UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=1 "
                "WHERE project_member_id=%s", (member,),
            )
        with runtime.unit_of_work() as tx:
            try:
                owner.read_exact(tx, query=read_query, source=frozen)
            except AIExecutionContentPlanError:
                pass
            else:
                raise AssertionError("suspended original actor was accepted")
        with connect(database_name) as db:
            db.execute(
                "UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=2 "
                "WHERE project_member_id=%s", (member,),
            )
        (result_root / first_stored.storage_locator).write_bytes(
            b"tampered synthetic result")
        with runtime.unit_of_work() as tx:
            try:
                owner.read_exact(tx, query=read_query, source=frozen)
            except AIExecutionContentPlanError:
                pass
            else:
                raise AssertionError("tampered exact result was accepted")

        with connect(database_name) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations").fetchone()[0] == 0
        print(
            "AI_04_A06_P03_P02_A03_DOCUMENT_CONTENT_PG_PASS: Windows 11, "
            "PostgreSQL 18, current actor authority and PROJECT scope locked; "
            "deterministic newest successful ParseRecord selected at planning; frozen "
            "older ParseRecord/ParseResult reread exactly after newer result appeared; "
            "canonical minimum UTF-8 text projection omitted locators; suspended actor "
            "and tampered private result rejected; no Invocation or Provider call"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(
                sql.Identifier(database_name)))
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-ai-document-content-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
