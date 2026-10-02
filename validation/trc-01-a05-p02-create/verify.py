"""Disposable PostgreSQL 18 TraceLink create, replay, authorization and rollback."""

from __future__ import annotations

import hashlib
import shutil
import socket
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.trace_document_owner import DocumentVersionTraceOwner
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
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
from plm_assistant.modules.trace.application.query_one_hop import (
    TraceOneHopQuery, TraceOneHopService, TraceQueryError,
)
from plm_assistant.modules.trace.application.query_bounded_graph import (
    TraceBoundedGraphQuery, TraceBoundedGraphService,
)
from plm_assistant.modules.trace.application.page_graph import (
    TraceGraphCursorCodec, TraceGraphPageService,
)
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, TraceRevokeError, TraceRevokeService,
)
from plm_assistant.modules.trace.application.supersede_link import (
    SupersedeTraceLink, TraceSupersedeError, TraceSupersedeService,
)
from plm_assistant.modules.trace.api.revoke_link import create_trace_revoke_router
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProofError,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.create_repository import SqlAlchemyTraceCreateRepository
from plm_assistant.modules.trace.infrastructure.query_repository import SqlAlchemyTraceAdjacencyRepository
from plm_assistant.modules.trace.infrastructure.revoke_repository import SqlAlchemyTraceRevokeRepository
from plm_assistant.modules.trace.infrastructure.supersede_repository import SqlAlchemyTraceSupersedeRepository
from plm_assistant.modules.trace.infrastructure.cycle_guard import (
    SqlAlchemyTraceCycleGuard, TraceCycleError,
)


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
CSRF = b"c" * 32
HASH = b"h" * 32


def run(*args: str, detached: bool = False) -> None:
    output = subprocess.DEVNULL if detached else subprocess.PIPE
    result = subprocess.run(args, stdout=output, stderr=output, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def create_user(db, name, token, role="NONE"):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role),
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
        pm_token, customer_token, im_token, other_pm_token, admin_token = (
            b"p" * 32, b"u" * 32, b"i" * 32, b"z" * 32, b"a" * 32,
        )
        with connect(name) as db:
            pm = create_user(db, "Trace PM", pm_token)
            customer = create_user(db, "Trace Customer", customer_token)
            implementer = create_user(db, "Trace Implementer", im_token)
            other_pm = create_user(db, "Trace Other PM", other_pm_token)
            deployment_admin = create_user(
                db, "Trace Deployment Admin", admin_token, "DEPLOYMENT_ADMIN",
            )
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
            global_doc = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES "
                "('GLOBAL',NULL,'STANDARD_CAPABILITY','Trace global','global.pdf',%s) "
                "RETURNING document_id", (deployment_admin,),
            ).fetchone()[0]
            global_file = db.execute(
                "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                "size_bytes,detected_mime,available_at) VALUES "
                "('GLOBAL',NULL,'PERSISTENT',%s,'global.pdf',%s,'AVAILABLE',%s,7,"
                "'application/pdf',%s) RETURNING file_object_id",
                (f"synthetic/{uuid.uuid4().hex}", deployment_admin, HASH,
                 datetime.now(timezone.utc) + timedelta(minutes=1)),
            ).fetchone()[0]
            global_version = db.execute(
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                "version_no,file_object_id,content_sha256,size_bytes,detected_mime,created_by) "
                "VALUES (%s,'GLOBAL',NULL,1,%s,%s,7,'application/pdf',%s) "
                "RETURNING document_version_id",
                (global_doc, global_file, HASH, deployment_admin),
            ).fetchone()[0]
        runtime = create_database_runtime(url)
        guard = Guard()
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        document_owner = DocumentVersionTraceOwner(documents)
        proofs = TraceTargetProofService({
            ("document", "DOC-02"): document_owner,
        })
        def resolved(token, path_project, document, version):
            with runtime.unit_of_work() as transaction:
                return document_owner.resolve(
                    transaction, TraceProofQuery(token, uuid.uuid4()), path_project,
                    TraceResourceVersionRef("DOC-02", document, version),
                )
        assert resolved(pm_token, project_id, doc_id, first) == TraceVersionRef(
            "document", "DOC-02", doc_id, first, "PROJECT", project_id,
        )
        assert resolved(admin_token, project_id, global_doc, global_version) == TraceVersionRef(
            "document", "DOC-02", global_doc, global_version, "GLOBAL", None,
        )
        for token, path, document, version in (
            (other_pm_token, project_id, doc_id, first),
            (pm_token, other_project, doc_id, first),
            (pm_token, project_id, doc_id, uuid.uuid4()),
            (pm_token, project_id, global_doc, global_version),
        ):
            try:
                resolved(token, path, document, version)
            except TraceTargetProofError as exc:
                assert exc.code == "RESOURCE_NOT_FOUND"
            else:
                raise AssertionError("unproved three-field Document ref resolved")
        with connect(name) as db:
            db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                       "WHERE file_object_id=%s", (global_file,))
        try:
            resolved(admin_token, project_id, global_doc, global_version)
        except TraceTargetProofError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("unavailable GLOBAL version resolved")
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
        reader = TraceOneHopService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectReadAccess(), projects=auth,
            license_guard=guard, proofs=proofs,
            repository=SqlAlchemyTraceAdjacencyRepository(),
        )
        graph = TraceBoundedGraphService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectReadAccess(), projects=auth,
            license_guard=guard, proofs=proofs,
            repository=SqlAlchemyTraceAdjacencyRepository(),
        )
        graph_pages = TraceGraphPageService(
            graph=graph, cursor_codec=TraceGraphCursorCodec(b"t" * 32),
            clock=lambda: datetime.now(timezone.utc),
        )
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
            concurrent_result = futures[0].result(timeout=10)
            assert concurrent_result == futures[1].result(timeout=10)
        with connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.trc_links").fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_CREATED'",
            ).fetchone()[0] == 2
        downstream = reader.query(TraceOneHopQuery(
            customer_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
        ))
        assert len(downstream.links) == 1 and downstream.links[0].edge == edge
        upstream = reader.query(TraceOneHopQuery(
            pm_token, uuid.uuid4(), project_id, ref(second), "UPSTREAM",
        ))
        assert len(upstream.links) == 1 and upstream.links[0].edge == edge
        limited = reader.query(TraceOneHopQuery(
            pm_token, uuid.uuid4(), project_id, ref(second), "DOWNSTREAM",
            relation_type="REFINES", limit=1,
        ))
        assert len(limited.links) == 1 and limited.links[0].edge == concurrent_edge
        graph_result = graph.query(TraceBoundedGraphQuery(
            customer_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
        ))
        assert graph_result.nodes == (ref(first), ref(second), ref(third))
        assert tuple(link.edge for link in graph_result.links) == (edge, concurrent_edge)
        assert not graph_result.truncated
        depth_one = graph.query(TraceBoundedGraphQuery(
            pm_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
            max_depth=1,
        ))
        assert depth_one.nodes == (ref(first), ref(second))
        assert tuple(link.edge for link in depth_one.links) == (edge,)
        page_query = TraceBoundedGraphQuery(
            customer_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
        )
        first_page = graph_pages.query_page(page_query, page_size=1)
        assert tuple(link.edge for link in first_page.links) == (edge,)
        assert first_page.next_cursor is not None
        second_page = graph_pages.query_page(
            page_query, page_size=1, cursor=first_page.next_cursor,
        )
        assert tuple(link.edge for link in second_page.links) == (concurrent_edge,)
        assert second_page.next_cursor is None
        try:
            reader.query(TraceOneHopQuery(
                other_pm_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
            ))
        except TraceQueryError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("cross-project actor read Trace graph")
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
        hidden = reader.query(TraceOneHopQuery(
            pm_token, uuid.uuid4(), project_id, ref(second), "DOWNSTREAM",
        ))
        assert hidden.links == () and hidden.truncated
        hidden_graph = graph.query(TraceBoundedGraphQuery(
            pm_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
        ))
        assert hidden_graph.nodes == (ref(first), ref(second))
        assert tuple(link.edge for link in hidden_graph.links) == (edge,)
        assert hidden_graph.truncated
        try:
            graph_pages.query_page(page_query, page_size=1,
                                   cursor=first_page.next_cursor)
        except TraceQueryError as exc:
            assert exc.code == "TRACE_CURSOR_STALE"
        else:
            raise AssertionError("revoked graph continued with stale cursor")
        fresh_hidden_page = graph_pages.query_page(page_query, page_size=1)
        assert tuple(link.edge for link in fresh_hidden_page.links) == (edge,)
        assert fresh_hidden_page.truncated and fresh_hidden_page.next_cursor is None
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
            resolved(pm_token, project_id, doc_id, first)
        except TraceTargetProofError as exc:
            assert exc.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License resolved Document version")
        try:
            reader.query(TraceOneHopQuery(
                pm_token, uuid.uuid4(), project_id, ref(first), "DOWNSTREAM",
            ))
        except TraceQueryError as exc:
            assert exc.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License permitted Trace read")
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
        def revoker(audit):
            return TraceRevokeService(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(), projects=auth,
                license_guard=guard,
                repository=SqlAlchemyTraceRevokeRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
            )
        revoke = revoker(AuditService(SqlAlchemyAuditRepository()))
        restricted_cmd = RevokeTraceLink(
            pm_token, CSRF, uuid.uuid4(), project_id,
            concurrent_result.trace_link_id, 0,
        )
        for denied, expected in (
            (RevokeTraceLink(customer_token, CSRF, uuid.uuid4(), project_id,
                             concurrent_result.trace_link_id, 0), "RESOURCE_NOT_FOUND"),
            (RevokeTraceLink(im_token, CSRF, uuid.uuid4(), project_id,
                             concurrent_result.trace_link_id, 0), "RESOURCE_NOT_FOUND"),
            (RevokeTraceLink(other_pm_token, CSRF, uuid.uuid4(), project_id,
                             concurrent_result.trace_link_id, 0), "RESOURCE_NOT_FOUND"),
            (RevokeTraceLink(pm_token, b"x" * 32, uuid.uuid4(), project_id,
                             concurrent_result.trace_link_id, 0), "AUTH_ACCESS_DENIED"),
            (RevokeTraceLink(pm_token, CSRF, uuid.uuid4(), other_project,
                             concurrent_result.trace_link_id, 0), "RESOURCE_NOT_FOUND"),
            (RevokeTraceLink(pm_token, CSRF, uuid.uuid4(), project_id,
                             concurrent_result.trace_link_id, 1), "CONFLICT_VERSION"),
        ):
            try:
                revoke.revoke(denied, idempotency_key="trace-revoke-denied-001")
            except TraceRevokeError as exc:
                assert exc.code == expected
            else:
                raise AssertionError("unauthorized or stale Trace revoke accepted")
        guard.enabled = False
        try:
            revoke.revoke(restricted_cmd, idempotency_key="trace-revoke-license-001")
        except TraceRevokeError as exc:
            assert exc.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License revoked TraceLink")
        guard.enabled = True
        restricted_result = revoke.revoke(
            restricted_cmd, idempotency_key="trace-revoke-first-001",
        )
        assert restricted_result.trace_link_id == concurrent_result.trace_link_id
        assert restricted_result.lock_version == 1
        assert revoke.revoke(
            restricted_cmd, idempotency_key="trace-revoke-first-001",
        ) == restricted_result
        try:
            revoke.revoke(restricted_cmd, idempotency_key="trace-revoke-second-001")
        except TraceRevokeError as exc:
            assert exc.code == "CONFLICT_VERSION"
        else:
            raise AssertionError("second TraceLink revoke accepted")
        rollback_created = creator.create(
            CreateTraceLink(pm_token, CSRF, uuid.uuid4(), rollback_edge),
            idempotency_key="trace-create-for-revoke-001",
        )
        rollback_command = RevokeTraceLink(
            pm_token, CSRF, uuid.uuid4(), project_id,
            rollback_created.trace_link_id, 0,
        )
        try:
            revoker(FailingAudit()).revoke(
                rollback_command, idempotency_key="trace-revoke-audit-fail-001",
            )
        except TraceRevokeError as exc:
            assert exc.code == "TRACE_UNAVAILABLE"
        else:
            raise AssertionError("Trace revoke audit failure committed")
        first_command = RevokeTraceLink(
            pm_token, CSRF, uuid.uuid4(), project_id,
            first_result.trace_link_id, 0,
        )
        barrier = Barrier(2)
        def concurrent_revoke():
            barrier.wait(timeout=5)
            return revoke.revoke(first_command, idempotency_key="trace-revoke-race-001")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(concurrent_revoke), pool.submit(concurrent_revoke))
            assert futures[0].result(timeout=15) == futures[1].result(timeout=15)
        with connect(name) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.trc_links WHERE link_state='REVOKED' "
                "AND lock_version=1",
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT link_state,lock_version FROM plm.trc_links "
                "WHERE trace_link_id=%s", (rollback_created.trace_link_id,),
            ).fetchone() == ("ACTIVE", 0)
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_REVOKED'",
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_TRACE_LINK_REVOKE'",
            ).fetchone()[0] == 2
        audit_service = AuditService(SqlAlchemyAuditRepository())
        http_sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
            audit=audit_service,
        )
        http_router = create_trace_revoke_router(
            sessions=http_sessions, revokes=revoke,
            origins=LoginOriginPolicy(["http://localhost"]),
        )
        http_path = (f"/api/v1/projects/{project_id}/trace-links/"
                     f"{rollback_created.trace_link_id}:revoke")
        http_headers = {
            "origin": "http://localhost",
            "cookie": "plm_session=" + pm_token.hex(),
            "x-csrf-token": CSRF.hex(),
            "idempotency-key": "trace-http-revoke-001",
            "if-match": '"v0"',
        }
        with TestClient(create_app(), base_url="http://localhost") as closed:
            assert closed.post(http_path, headers=http_headers).status_code == 404
        with TestClient(create_app(trace_revoke_router=http_router),
                        base_url="http://localhost") as client:
            def post(headers, status, code=None, path=http_path, content=None):
                response = client.post(path, headers=headers, content=content)
                assert response.status_code == status, response.text
                if code is not None:
                    assert response.json()["error"]["code"] == code, response.text
                return response

            post(http_headers | {"cookie": "plm_session=" + customer_token.hex()},
                 404, "RESOURCE_NOT_FOUND")
            post(http_headers | {"x-csrf-token": (b"x" * 32).hex()},
                 403, "AUTH_CSRF_INVALID")
            post({key: value for key, value in http_headers.items()
                  if key != "if-match"}, 428, "CONFLICT_VERSION_REQUIRED")
            post(http_headers, 400, "REQUEST_MALFORMED", content=b"{}")
            post(http_headers, 400, "REQUEST_MALFORMED", path=http_path + "?x=1")
            guard.enabled = False
            post(http_headers, 403, "LICENSE_OPERATION_DENIED")
            guard.enabled = True
            first_http = post(http_headers, 200)
            assert first_http.headers["etag"] == '"v1"'
            assert first_http.json()["data"] == {
                "trace_link_id": str(rollback_created.trace_link_id),
                "link_state": "REVOKED",
            }
            assert post(http_headers, 200).json()["data"] == first_http.json()["data"]
            post(http_headers | {"if-match": '"v1"'}, 409, "CONFLICT_IDEMPOTENCY")
            post(http_headers | {"idempotency-key": "trace-http-revoke-002"},
                 409, "CONFLICT_VERSION")
        with connect(name) as db:
            assert db.execute(
                "SELECT link_state,lock_version FROM plm.trc_links "
                "WHERE trace_link_id=%s", (rollback_created.trace_link_id,),
            ).fetchone() == ("REVOKED", 1)
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_REVOKED'",
            ).fetchone()[0] == 3
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_TRACE_LINK_REVOKE' AND state='COMPLETED'",
            ).fetchone()[0] == 3
        def superseder(audit):
            return TraceSupersedeService(
                unit_of_work=runtime.unit_of_work,
                sessions=SqlAlchemyProjectWriteAccess(), projects=auth,
                license_guard=guard, proofs=proofs,
                cycle_guard=SqlAlchemyTraceCycleGuard(),
                repository=SqlAlchemyTraceSupersedeRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
            )
        supersede = superseder(AuditService(SqlAlchemyAuditRepository()))
        old_edge = TraceEdgeShape(ref(second), ref(first), "REFINES")
        new_edge = TraceEdgeShape(ref(second), ref(first), "IMPLEMENTS")
        old_link = creator.create(
            CreateTraceLink(pm_token, CSRF, uuid.uuid4(), old_edge),
            idempotency_key="trace-create-for-supersede-001",
        )
        change = SupersedeTraceLink(
            pm_token, CSRF, uuid.uuid4(), project_id,
            old_link.trace_link_id, 0, new_edge,
        )
        for denied, expected in (
            (SupersedeTraceLink(customer_token, CSRF, uuid.uuid4(), project_id,
                                old_link.trace_link_id, 0, new_edge), "RESOURCE_NOT_FOUND"),
            (SupersedeTraceLink(pm_token, CSRF, uuid.uuid4(), other_project,
                                old_link.trace_link_id, 0, new_edge), "VALIDATION_FAILED"),
            (SupersedeTraceLink(pm_token, CSRF, uuid.uuid4(), project_id,
                                old_link.trace_link_id, 1, new_edge), "CONFLICT_VERSION"),
            (SupersedeTraceLink(pm_token, CSRF, uuid.uuid4(), project_id,
                                old_link.trace_link_id, 0, old_edge), "VALIDATION_FAILED"),
        ):
            try:
                supersede.supersede(denied, idempotency_key="trace-supersede-denied-001")
            except TraceSupersedeError as exc:
                assert exc.code == expected, (exc.code, expected)
            else:
                raise AssertionError("invalid Trace replacement accepted")
        guard.enabled = False
        try:
            supersede.supersede(change, idempotency_key="trace-supersede-license-001")
        except TraceSupersedeError as exc:
            assert exc.code == "LICENSE_OPERATION_DENIED"
        else:
            raise AssertionError("expired License replaced TraceLink")
        guard.enabled = True
        try:
            superseder(FailingAudit()).supersede(
                change, idempotency_key="trace-supersede-audit-fail-001",
            )
        except TraceSupersedeError as exc:
            assert exc.code == "TRACE_UNAVAILABLE"
        else:
            raise AssertionError("Trace supersede audit failure committed")
        with connect(name) as db:
            assert db.execute(
                "SELECT link_state,lock_version,superseded_by_ref FROM plm.trc_links "
                "WHERE trace_link_id=%s", (old_link.trace_link_id,),
            ).fetchone() == ("ACTIVE", 0, None)
            assert db.execute(
                "SELECT count(*) FROM plm.trc_links WHERE relation_type='IMPLEMENTS' "
                "AND source_version_id=%s AND target_version_id=%s",
                (second, first),
            ).fetchone()[0] == 0
        barrier = Barrier(2)
        def concurrent_supersede():
            barrier.wait(timeout=5)
            return supersede.supersede(
                change, idempotency_key="trace-supersede-race-001",
            )
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(concurrent_supersede),
                       pool.submit(concurrent_supersede))
            first_replacement = futures[0].result(timeout=15)
            assert futures[1].result(timeout=15) == first_replacement
        try:
            supersede.supersede(change, idempotency_key="trace-supersede-new-001")
        except TraceSupersedeError as exc:
            assert exc.code == "CONFLICT_VERSION"
        else:
            raise AssertionError("second replacement accepted")
        with connect(name) as db:
            assert db.execute(
                "SELECT link_state,lock_version,superseded_by_ref FROM plm.trc_links "
                "WHERE trace_link_id=%s", (old_link.trace_link_id,),
            ).fetchone() == ("SUPERSEDED", 1, first_replacement.replacement_id)
            assert db.execute(
                "SELECT link_state,lock_version FROM plm.trc_links "
                "WHERE trace_link_id=%s", (first_replacement.replacement_id,),
            ).fetchone() == ("ACTIVE", 0)
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='TRACE_LINK_SUPERSEDED'",
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE operation='V1_TRACE_LINK_SUPERSEDE' AND state='COMPLETED'",
            ).fetchone()[0] == 1
        colliding_old = creator.create(
            CreateTraceLink(pm_token, CSRF, uuid.uuid4(),
                            TraceEdgeShape(ref(first), ref(second), "VALIDATES")),
            idempotency_key="trace-supersede-collision-old-001",
        )
        existing_target = creator.create(
            CreateTraceLink(pm_token, CSRF, uuid.uuid4(), edge),
            idempotency_key="trace-supersede-collision-target-001",
        )
        try:
            supersede.supersede(SupersedeTraceLink(
                pm_token, CSRF, uuid.uuid4(), project_id,
                colliding_old.trace_link_id, 0, edge,
            ), idempotency_key="trace-supersede-collision-001")
        except TraceSupersedeError as exc:
            assert exc.code == "CONFLICT_STATE"
        else:
            raise AssertionError("pre-existing active edge reused as replacement")
        with connect(name) as db:
            assert db.execute(
                "SELECT link_state,lock_version,superseded_by_ref FROM plm.trc_links "
                "WHERE trace_link_id=%s", (colliding_old.trace_link_id,),
            ).fetchone() == ("ACTIVE", 0, None)
            assert db.execute(
                "SELECT link_state FROM plm.trc_links WHERE trace_link_id=%s",
                (existing_target.trace_link_id,),
            ).fetchone() == ("ACTIVE",)
            db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s",
                       (project_id,))
        try:
            creator.create(CreateTraceLink(pm_token, CSRF, uuid.uuid4(), rollback_edge),
                           idempotency_key="trace-archived-key-001")
        except TraceCreateError as exc:
            assert exc.code == "PROJECT_ARCHIVED"
        else:
            raise AssertionError("archived project accepted Trace write")
        print("PASS: Trace create/graph, PM revoke HTTP and atomic PM supersede/PG chain")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


def main() -> None:
    global PORT
    scratch = Path(tempfile.mkdtemp(prefix="plm-trc-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    started = False
    bin_dir = install / "bin"
    data = scratch / "data"
    try:
        for name in ("bin", "lib", "share"):
            shutil.copytree(PG_SOURCE / name, install / name)
        shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
        shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
        for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
            shutil.copy2(path, install / "share/extension" / path.name)
        PORT = free_port()
        run(str(bin_dir / "initdb.exe"), "-D", str(data), "-U", USER,
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
            "-o", f"-h {HOST} -p {PORT}", "-w", "start", detached=True)
        started = True
        verify()
    finally:
        if started:
            run(str(bin_dir / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        if data.exists():
            status = subprocess.run([str(bin_dir / "pg_ctl.exe"), "-D", str(data), "status"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=15)
            if status.returncode == 0:
                raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-trc-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
