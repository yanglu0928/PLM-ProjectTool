"""Disposable PostgreSQL 18 TraceLink create, replay, authorization and rollback."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.trace_document_owner import DocumentVersionTraceOwner
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.trace.application.create_link import (
    CreateTraceLink, TraceCreateError, TraceCreateService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceTargetProofError, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository
from plm_assistant.modules.trace.infrastructure.cycle_guard import (
    SqlAlchemyTraceCycleGuard, TraceCycleError,
)


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32
HASH = b"h" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def create_user(db, name, token):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,'NONE') RETURNING user_id", (name, name.lower()),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, user_id),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id),
    )
    return user_id


def create_version(db, document_id, project_id, actor, number, previous):
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,created_by,file_state,sha256,"
        "size_bytes,detected_mime,available_at) VALUES "
        "('PROJECT',%s,'PERSISTENT',%s,'synthetic.pdf',%s,'AVAILABLE',%s,7,"
        "'application/pdf',%s) RETURNING file_object_id",
        (project_id, f"synthetic/{uuid.uuid4().hex}", actor, HASH,
         datetime.now(timezone.utc) + timedelta(minutes=1)),
    ).fetchone()[0]
    version_id = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,created_by,"
        "supersedes_version_ref) VALUES (%s,'PROJECT',%s,%s,%s,%s,7,'application/pdf',%s,%s) "
        "RETURNING document_version_id",
        (document_id, project_id, number, file_id, HASH, actor, previous),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s,"
        "lock_version=lock_version+1 WHERE document_id=%s",
        (version_id, version_id, document_id),
    )
    return version_id, file_id


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def verify():
    name = "trace_create_" + uuid.uuid4().hex[:10]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=PORT, database=name)
        command.upgrade(create_migration_config(url), "head")
        pm_token, customer_token, im_token, other_pm_token = (
            b"p" * 32, b"u" * 32, b"i" * 32, b"z" * 32,
        )
        with connect(name) as db:
            pm = create_user(db, "Trace PM", pm_token)
            customer = create_user(db, "Trace Customer", customer_token)
            implementer = create_user(db, "Trace Implementer", im_token)
            other_pm = create_user(db, "Trace Other PM", other_pm_token)
            project_id = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('TR1','tr1','Trace Project',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            dept_id = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                "RETURNING department_id", (project_id,),
            ).fetchone()[0]
            for actor, role in ((pm, "PROJECT_MANAGER"),
                                (customer, "CUSTOMER_MEMBER"),
                                (implementer, "IMPLEMENTATION_MEMBER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)", (project_id, actor, dept_id, role),
                )
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('TR2','tr2','Trace Other Project',%s) RETURNING project_id", (other_pm,),
            ).fetchone()[0]
            other_dept = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                "RETURNING department_id", (other_project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (other_project, other_pm, other_dept),
            )
            doc_id = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES "
                "('PROJECT',%s,'PROJECT_RECORD','Trace source','source.pdf',%s) "
                "RETURNING document_id", (project_id, pm),
            ).fetchone()[0]
            with db.transaction():
                first, _ = create_version(db, doc_id, project_id, pm, 1, None)
            with db.transaction():
                second, _ = create_version(db, doc_id, project_id, pm, 2, first)
            with db.transaction():
                third, third_file = create_version(db, doc_id, project_id, pm, 3, second)
        runtime = create_database_runtime(url)
        guard = Guard()
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        proofs = TraceTargetProofService({
            ("document", "DOC-02"): DocumentVersionTraceOwner(documents),
        })
        auth = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        def service(audit):
            return TraceCreateService(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(), projects=auth,
                proofs=proofs, cycle_guard=SqlAlchemyTraceCycleGuard(),
                repository=SqlAlchemyTraceCreateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
            )
        creator = service(AuditService(SqlAlchemyAuditRepository()))
        ref = lambda version: TraceVersionRef(
            "document", "DOC-02", doc_id, version, "PROJECT", project_id,
        )
        edge = TraceEdgeShape(ref(first), ref(second), "DERIVED_FROM")
        cmd = CreateTraceLink(pm_token, CSRF, uuid.uuid4(), edge)
        first_result = creator.create(cmd, idempotency_key="trace-create-key-001")
        assert creator.create(cmd, idempotency_key="trace-create-key-001") == first_result
        assert creator.create(cmd, idempotency_key="trace-create-key-002") == first_result
        im_result = creator.create(
            CreateTraceLink(im_token, CSRF, uuid.uuid4(), edge),
            idempotency_key="trace-create-key-003",
        )
        assert im_result == first_result
        with connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_CREATED'",
            ).fetchone()[0] == 1
        concurrent_edge = TraceEdgeShape(ref(second), ref(third), "REFINES")
        barrier = Barrier(2)
        def concurrent_create(token, key):
            barrier.wait(timeout=5)
            return creator.create(
                CreateTraceLink(token, CSRF, uuid.uuid4(), concurrent_edge),
                idempotency_key=key,
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(concurrent_create, pm_token, "trace-concurrent-key-1"),
                pool.submit(concurrent_create, im_token, "trace-concurrent-key-2"),
            )
            assert futures[0].result(timeout=10) == futures[1].result(timeout=10)
        with connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_CREATED'",
            ).fetchone()[0] == 2
        try:
            creator.create(CreateTraceLink(customer_token, CSRF, uuid.uuid4(), edge),
                           idempotency_key="trace-customer-key")
        except TraceCreateError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("customer created TraceLink")
        try:
            creator.create(CreateTraceLink(pm_token, b"x" * 32, uuid.uuid4(), edge),
                           idempotency_key="trace-bad-csrf-key")
        except TraceCreateError as exc:
            assert exc.code == "AUTH_ACCESS_DENIED"
        else:
            raise AssertionError("bad CSRF created TraceLink")
        reverse = TraceEdgeShape(ref(second), ref(first), "DERIVED_FROM")
        try:
            creator.create(CreateTraceLink(pm_token, CSRF, uuid.uuid4(), reverse),
                           idempotency_key="trace-cycle-key-001")
        except TraceCycleError:
            pass
        else:
            raise AssertionError("cycle created TraceLink")
        with connect(name) as db:
            db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                       "WHERE file_object_id=%s", (third_file,))
        unavailable = TraceEdgeShape(ref(first), ref(third), "REFINES")
        try:
            creator.create(CreateTraceLink(pm_token, CSRF, uuid.uuid4(), unavailable),
                           idempotency_key="trace-restricted-key")
        except TraceTargetProofError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("restricted target created TraceLink")
        forged_source = TraceVersionRef(
            "document", "DOC-02", doc_id, first, "PROJECT", other_project,
        )
        forged_target = TraceVersionRef(
            "document", "DOC-02", doc_id, second, "PROJECT", other_project,
        )
        try:
            creator.create(CreateTraceLink(
                other_pm_token, CSRF, uuid.uuid4(),
                TraceEdgeShape(forged_source, forged_target, "REFINES"),
            ), idempotency_key="trace-cross-project-key")
        except TraceTargetProofError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("cross-project DocumentVersion became Trace target")
        guard.enabled = False
        try:
            creator.create(CreateTraceLink(pm_token, CSRF, uuid.uuid4(), edge),
                           idempotency_key="trace-expired-license-key")
        except TraceTargetProofError as exc:
            assert exc.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License permitted Trace creation")
        guard.enabled = True
        rollback_edge = TraceEdgeShape(ref(first), ref(second), "REFINES")
        try:
            service(FailingAudit()).create(
                CreateTraceLink(pm_token, CSRF, uuid.uuid4(), rollback_edge),
                idempotency_key="trace-audit-fail-key",
            )
        except RuntimeError as exc:
            assert str(exc) == "synthetic audit failure"
        else:
            raise AssertionError("audit failure did not fail command")
        with connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_TRACE_LINK_CREATE'",
            ).fetchone()[0] == 5
            db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s",
                       (project_id,))
        try:
            creator.create(CreateTraceLink(pm_token, CSRF, uuid.uuid4(), rollback_edge),
                           idempotency_key="trace-archived-key-001")
        except TraceCreateError as exc:
            assert exc.code == "PROJECT_ARCHIVED"
        else:
            raise AssertionError("archived project accepted Trace write")
        print("PASS: Trace create, replay, duplicate edge, roles/CSRF, cycle, target and Audit rollback")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
