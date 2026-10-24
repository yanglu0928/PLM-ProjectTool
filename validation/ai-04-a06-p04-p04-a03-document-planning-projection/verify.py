"""Windows/PostgreSQL proof for Document Preview planning projection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentIdentityQuery,
)
from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionInputRef,
)
from plm_assistant.modules.document.application.ai_content import (
    DocumentAIContentError,
    DocumentAIContentQuery,
    DocumentAIContentService,
)
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load_document_helper():
    path = (Path(__file__).resolve().parents[1]
            / "ai-04-a06-p03-p02-a03-document-content-pg" / "verify.py")
    spec = importlib.util.spec_from_file_location("ai_document_content_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    helper = load_document_helper()
    database = "ai04a06p04p04a03_" + uuid.uuid4().hex[:8]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    )
    scratch = Path(tempfile.mkdtemp(prefix="plm-ai-document-planning-"))
    runtime = None
    with helper.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        command.upgrade(create_migration_config(url), "head")
        (scratch / "results").mkdir()
        storage = LocalParseResultStorage(scratch / "results")
        with helper.connect(database) as db:
            actor = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('Preview Customer Manager','preview customer manager') "
                "RETURNING user_id",
            ).fetchone()[0]
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('AIDOCPRV1','aidocprv1',"
                "'Document planning projection',%s) RETURNING project_id", (actor,),
            ).fetchone()[0]
            department = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'CUS','cus','Customer') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                "project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')",
                (project, actor, department),
            )
            source_bytes = "合成Preview需求".encode("utf-8")
            source_sha = hashlib.sha256(source_bytes).digest()
            document = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                "'Synthetic Preview','preview.txt',%s) RETURNING document_id",
                (project, actor),
            ).fetchone()[0]
            file_id = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
                "storage_class,storage_locator,original_name_metadata,created_by,file_state,"
                "sha256,size_bytes,detected_mime,available_at) VALUES "
                "(%s,'PROJECT',%s,'PERSISTENT',%s,'preview.txt',%s,'AVAILABLE',"
                "%s,%s,'text/plain',statement_timestamp())",
                (file_id, project, f"projects/{project.hex}/preview.txt", actor,
                 source_sha, len(source_bytes)),
            )
            version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,%s,"
                "'text/plain',%s,%s) RETURNING document_version_id",
                (document, project, file_id, source_sha, len(source_bytes),
                 Jsonb({"synthetic": True}), actor),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                "WHERE document_id=%s", (version, version, document),
            )
            record, result_ref, _stored = helper.seed_result(
                db, storage, actor=actor, project=project, document=document,
                version=version, source_sha=source_sha, attempt=1,
                text="客户需求 A\r\n最小正文", completed_at=datetime.now(timezone.utc),
            )

        runtime = create_database_runtime(url)
        service = DocumentAIContentService(
            repository=SqlAlchemyDocumentAIContentRepository(), storage=storage,
            projects=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            license_guard=helper.Guard(),
        )
        owner = AIDocumentContentOwner(service)
        input_ref = AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            document, version, project,
        )
        query = AIExecutionContentIdentityQuery(
            uuid.uuid4(), project, actor, uuid.uuid4(), "project-gap-analysis.v1",
            "minimum.document.text.v1", owner.selection_policy_ref,
        )
        with runtime.unit_of_work() as transaction:
            projection = owner.resolve_projection(
                transaction, query=query, input_ref=input_ref,
            )
            payload = json.loads(projection.content_utf8)
            assert payload["nodes"][0]["text"] == "客户需求 A\n最小正文"
            assert projection.source.content_revision_id == record
            assert projection.source.content_object_id == result_ref
            assert projection.source.projection_fingerprint == hashlib.sha256(
                projection.content_utf8).digest()
            assert "客户需求" not in repr(projection)
            with helper.connect(database) as verifier:
                verifier.execute("SET lock_timeout='250ms'")
                try:
                    with verifier.transaction():
                        verifier.execute(
                            "UPDATE plm.doc_parse_records SET lock_version=lock_version+1 "
                            "WHERE parse_record_id=%s", (record,),
                        )
                except psycopg.Error as error:
                    assert error.sqlstate in {"55P03", "57014"}, error.sqlstate
                else:
                    raise AssertionError("Document planning projection did not retain locks")
            transaction.rollback()

        execution_query = DocumentAIContentQuery(
            project, actor, uuid.uuid4(), "project-gap-analysis.v1",
            "minimum.document.text.v1", owner.selection_policy_ref,
        )
        with runtime.unit_of_work() as transaction:
            try:
                service.resolve_identity(
                    transaction, query=execution_query, document_id=document,
                    document_version_id=version,
                )
            except DocumentAIContentError:
                pass
            else:
                raise AssertionError("Customer Manager received execute authority")
            transaction.rollback()

        with helper.connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.ai_execution_content_plans"
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations"
            ).fetchone()[0] == 0
        print(
            "AI_04_A06_P04_P04_A03_DOCUMENT_PLANNING_PROJECTION_PASS: exact current "
            "ParseRecord minimum projection, Preview-only CustomerManager authority, "
            "transaction locks, sensitive repr exclusion and zero provider I/O"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with helper.connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-ai-document-planning-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
