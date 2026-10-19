"""Disposable Win11/PG18.6 real HTTP reverse Trace for fixed synthetic WBS items."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_trace_graph import (
    ProductionTraceGraphStartupError, create_windows_trace_graph_router,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.plan.application.create_plan import CreatePlan, PlanCreateService
from plm_assistant.modules.plan.infrastructure.create_repository import SqlAlchemyPlanCreateRepository
from plm_assistant.modules.trace.application.page_graph import TraceGraphCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "trace_wbs_plan_fixture",
    ROOT / "validation/plan-01-a03-p02-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
        raise RuntimeLicenseError("EXPIRED")


def on_created(*, port, runtime, license_guard, project, other_project,
               manager, member, token, csrf, member_token, **_unused):
    audit = AuditService(SqlAlchemyAuditRepository())
    creator = PlanCreateService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyPlanCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    plan = creator.create(CreatePlan(
        token, csrf, uuid.uuid4(), project, "Trace graph synthetic plan", "g" * 16))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.pln_plan_versions "
                   "DISABLE TRIGGER trg_pln_plan_versions__owner")
        db.execute("ALTER TABLE plm.pln_wbs_items "
                   "DISABLE TRIGGER trg_pln_wbs_items__owner")
        try:
            version = db.execute(
                "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                (plan.plan_id, project, manager)).fetchone()[0]
            items = []
            for ordinal in (1, 2, 3):
                items.append(db.execute(
                    "INSERT INTO plm.pln_wbs_items"
                    "(plan_version_id,plan_id,project_id,wbs_code,name,level,ordinal) "
                    "VALUES (%s,%s,%s,%s,%s,1,%s) RETURNING wbs_item_id",
                    (version, plan.plan_id, project, str(ordinal),
                     f"Synthetic WBS {ordinal}", ordinal)).fetchone()[0])
        finally:
            db.execute("ALTER TABLE plm.pln_wbs_items "
                       "ENABLE TRIGGER trg_pln_wbs_items__owner")
            db.execute("ALTER TABLE plm.pln_plan_versions "
                       "ENABLE TRIGGER trg_pln_plan_versions__owner")
        for source in items[:2]:
            db.execute(
                "INSERT INTO plm.trc_links"
                "(scope,project_id,source_owner_module,source_object_type,"
                "source_object_id,source_version_id,source_project_id,"
                "target_owner_module,target_object_type,target_object_id,"
                "target_version_id,target_project_id,relation_type,created_by,trace_id) "
                "VALUES ('PROJECT',%s,'plan','PLN-02-WBS',%s,%s,%s,"
                "'plan','PLN-02-WBS',%s,%s,%s,'DERIVED_FROM',%s,%s)",
                (project, source, version, project, items[2], version,
                 project, manager, uuid.uuid4()))
        before_audit = db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0]
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = create_windows_trace_graph_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=TraceGraphCursorCodec(b"t" * 32))
    try:
        create_windows_trace_graph_router(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, cursors=None)
    except ProductionTraceGraphStartupError:
        pass
    else:
        raise AssertionError("missing graph cursor accepted")
    path = f"/api/v1/projects/{project}/trace-graph:upstream"
    params = {"resource_type": "PLN-02-WBS", "resource_id": str(items[2]),
              "version_id": str(version), "page_size": "1", "max_depth": "1"}
    headers = {"cookie": "plm_session=" + token.hex()}
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.get(path, params=params, headers=headers).status_code == 404
    with TestClient(create_app(trace_graph_router=router),
                    base_url="https://plm.example.test") as client:
        first = client.get(path, params=params, headers=headers)
        assert first.status_code == 200, first.text
        data = first.json()["data"]
        assert data["root"]["resource_id"] == str(items[2])
        assert len(data["links"]) == 1 and data["next_cursor"]
        sources = {data["links"][0]["source"]["resource_id"]}
        assert data["links"][0]["target"]["resource_id"] == str(items[2])
        second = client.get(path, params={**params, "cursor": data["next_cursor"]},
                            headers=headers)
        assert second.status_code == 200, second.text
        data2 = second.json()["data"]
        sources.add(data2["links"][0]["source"]["resource_id"])
        assert sources == {str(items[0]), str(items[1])}
        assert data2["next_cursor"] is None and not data2["truncated"]
        assert client.get(path, params={**params, "version_id": str(uuid.uuid4())},
                          headers=headers).status_code == 404
        assert client.get(path.replace(str(project), str(other_project)),
                          params=params, headers=headers).status_code == 404
        assert client.get(path, params=params, headers={}).status_code == 401
        member_headers = {"cookie": "plm_session=" + member_token.hex()}
        member_first = client.get(path, params=params, headers=member_headers)
        assert member_first.status_code == 200, member_first.text
        member_cursor = member_first.json()["data"]["next_cursor"]
        assert member_cursor
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',"
                       "lock_version=lock_version+1 WHERE user_id=%s AND project_id=%s",
                       (member, project))
        assert client.get(path, params=params, headers=member_headers).status_code == 404
        assert client.get(path, params={**params, "cursor": member_cursor},
                          headers=member_headers).status_code == 404
    denied_router = create_windows_trace_graph_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=DeniedLicense(), cursors=TraceGraphCursorCodec(b"t" * 32))
    with TestClient(create_app(trace_graph_router=denied_router),
                    base_url="https://plm.example.test") as denied:
        assert denied.get(path, params=params, headers=headers).status_code == 403
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == before_audit
    return 0


if __name__ == "__main__":
    prior.prior.main(on_created=on_created)
    print("PLAN_02_A04_P04_A04_P02_A03_P02_A01_WINDOWS_TRACE_GRAPH_PASS: "
          "real Session/ASGI/PG fixed WBS reverse pages, isolation, revocation, "
          "License and zero read Audit")
