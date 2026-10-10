"""Windows 11/PostgreSQL 18 proof for HandoverAnalysis identity creation."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.handover.application.create_analysis import (
    CreateHandoverAnalysis, HandoverAnalysisCreateError,
    HandoverAnalysisCreateService,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef, HandoverSourceValidator,
)
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import (
    SqlAlchemyHandoverAnalysisCreateRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
connect, seed_user = helpers["connect"], helpers["seed_user"]
Guard, FailedAudit, CSRF = helpers["Guard"], helpers["FailedAudit"], helpers["CSRF"]


def expect(code: str, action) -> None:
    try:
        action()
    except HandoverAnalysisCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def seed_project_document(db, actor, project, suffix):
    file_id, document_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
            "storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,file_state,"
            "created_by,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,%s,%s,16,"
            "'application/pdf','AVAILABLE',%s,statement_timestamp())",
            (file_id, project, f"handover/{suffix}.pdf", f"{suffix}.pdf", b"d" * 32, actor),
        )
        db.execute(
            "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,title,"
            "original_display_name,document_state,created_by) VALUES (%s,'PROJECT',%s,"
            "'PROJECT_RECORD',%s,%s,'ACTIVE',%s)",
            (document_id, project, f"Handover {suffix}", f"{suffix}.pdf", actor),
        )
        db.execute(
            "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,project_id,"
            "version_no,file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
            "created_by,availability_state,integrity_checked_at) VALUES (%s,%s,'PROJECT',%s,1,%s,"
            "%s,16,'application/pdf','{}'::jsonb,%s,'AVAILABLE',statement_timestamp())",
            (version_id, document_id, project, file_id, b"d" * 32, actor),
        )
    return HandoverDocumentRef(document_id, version_id)


def main() -> None:
    name = "hnd01a03p01_" + uuid.uuid4().hex[:9]
    pm_token, impl_token, customer_token = b"p" * 32, b"i" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = seed_user(db, "Handover PM", "NONE", pm_token)
                    impl = seed_user(db, "Handover Implementer", "NONE", impl_token)
                    customer = seed_user(db, "Handover Customer", "NONE", customer_token)
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,"
                        "created_by) VALUES ('HNDP01','hndp01','Handover Project',%s) RETURNING project_id",
                        (pm,),
                    ).fetchone()[0]
                    other = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,"
                        "created_by) VALUES ('HNDP02','hndp02','Other Project',%s) RETURNING project_id",
                        (pm,),
                    ).fetchone()[0]
                    department = db.execute(
                        "INSERT INTO plm.prj_departments(project_id,department_code,"
                        "department_code_normalized,name) VALUES (%s,'HND','hnd','Handover') "
                        "RETURNING department_id", (project,),
                    ).fetchone()[0]
                    for user, role in ((pm, "PROJECT_MANAGER"),
                                       (impl, "IMPLEMENTATION_MEMBER"),
                                       (customer, "CUSTOMER_MANAGER")):
                        db.execute(
                            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                            "project_role) VALUES (%s,%s,%s,%s)",
                            (project, user, department, role),
                        )
                    source = seed_project_document(db, pm, project, "source")
                    foreign_source = seed_project_document(db, pm, other, "foreign")

                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                common = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=authorization,
                    sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository()),
                    repository=SqlAlchemyHandoverAnalysisCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def service(audit=None):
                    return HandoverAnalysisCreateService(
                        **common, audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    )

                def create(*, token=pm_token, csrf=CSRF, purpose="Project handover",
                           sources=(source,), key=None, target=None):
                    return (target or service()).create(CreateHandoverAnalysis(
                        token, csrf, uuid.uuid4(), project, purpose, sources,
                        key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                expect("RESOURCE_NOT_FOUND", lambda: create(token=customer_token))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True
                expect("HANDOVER_SOURCE_UNAVAILABLE", lambda: create(
                    sources=(foreign_source,),
                ))

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(
                    key=first_key, purpose="Changed purpose",
                ))
                implemented = create(token=impl_token, purpose="Implementation handover")
                assert implemented.project_id == project

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(
                        key=concurrent_key, purpose="Concurrent handover",
                    ), range(2)))
                assert results[0] == results[1]

                rollback_key = str(uuid.uuid4())
                expect("HANDOVER_UNAVAILABLE", lambda: create(
                    key=rollback_key, purpose="Rollback handover",
                    target=service(FailedAudit()),
                ))
                recovered = create(key=rollback_key, purpose="Rollback handover")
                assert recovered.handover_analysis_id not in {
                    first.handover_analysis_id, implemented.handover_analysis_id,
                }

                with connect(name) as db:
                    row = db.execute(
                        "SELECT project_id,analysis_purpose,source_set_ref,analysis_state,"
                        "current_approved_version_ref,lock_version FROM plm.hnd_analyses "
                        "WHERE handover_analysis_id=%s", (first.handover_analysis_id,),
                    ).fetchone()
                    assert row == (
                        project, "Project handover", first.source_set_ref,
                        "ACTIVE", None, 0,
                    ), row
                    assert db.execute(
                        "SELECT count(*) FROM plm.hnd_analysis_versions"
                    ).fetchone()[0] == 0
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE "
                        "action='HND_ANALYSIS_CREATED' AND target_object_id=%s",
                        (first.handover_analysis_id,),
                    ).fetchone()[0] == 1
                    assert db.execute(
                        "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                        "operation='V1_HND_ANALYSIS_CREATE'"
                    ).fetchone()[0] == 4
                    db.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s", (project, pm),
                    )
                expect("RESOURCE_NOT_FOUND", lambda: create(key=first_key))
                print(
                    "HND_01_A03_P01_ANALYSIS_CREATE_PASS: PM/Implementation role, "
                    "Session/CSRF/License, fixed PROJECT source, replay/concurrency, "
                    "Audit rollback, zero-Version boundary and role revocation verified "
                    "on PostgreSQL 18"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
