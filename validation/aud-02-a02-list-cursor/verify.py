"""Isolated PostgreSQL signed pagination; real Session/Project, synthetic License."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid
from psycopg import sql
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.api.search_resolver import AuditCursorSearchResolver
from plm_assistant.modules.platform.application.errors import ApplicationError

spec = spec_from_file_location("_audit_cursor_fixture", Path(__file__).resolve().parents[1] / "aud-02-a01-authorized-read" / "verify.py")
f = module_from_spec(spec)
spec.loader.exec_module(f)


def main(*,resolved=False,http=False,platform_check=None):
    name, runtime = "auditcursor_" + uuid.uuid4().hex[:12], None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(f.create_migration_config(url), "head")
            runtime = f.create_database_runtime(url)
            with f.schema.connect(name) as db:
                session, admin_session = b"s" * 32, b"a" * 32
                actor = f.auth.user(db, "Synthetic cursor PM", session, "NONE")
                admin_actor = f.auth.user(db, "Synthetic cursor admin", admin_session, "DEPLOYMENT_ADMIN")
                project = f.schema.insert(db, "prj_projects", dict(project_code="CURSOR", project_code_normalized="cursor", name="Synthetic cursor project", created_by=actor), "project_id")
                dept = f.schema.insert(db, "prj_departments", dict(project_id=project, department_code="D", department_code_normalized="d", name="Synthetic department"), "department_id")
                f.schema.insert(db, "prj_project_members", dict(project_id=project, user_id=actor, department_id=dept, project_role="PROJECT_MANAGER"), "project_member_id")
                writer = f.AuditService(f.SqlAlchemyAuditRepository())

                def append(scope):
                    with runtime.unit_of_work() as tx:
                        result = writer.append(tx, f.AuditEventDraft(trace_id=uuid.uuid4(), event_scope="DEPLOYMENT" if scope is None else "PROJECT", target_project_id=scope, actor_type="USER", actor_id=actor, original_actor_id=None, actor_hint_digest=None, action="SYNTHETIC_CURSOR_EVENT", outcome="SUCCESS"))
                        tx.commit()
                        return result

                local = [append(project) for _ in range(3)]
                deployed = [append(None) for _ in range(3)]
                service = f.AuthorizedAuditReadService(unit_of_work=runtime.unit_of_work, project_access=f.SqlAlchemyProjectReadAccess(), deployment_access=f.SqlAlchemyDeploymentReadAccess(), projects=f.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=f.SqlAlchemyProjectAuthorizationRepository()), license_guard=f.auth.Guard(), repository=f.SqlAlchemyAuditReadRepository())
                now = datetime.now(timezone.utc)
                search = f.AuditSearch(now - timedelta(days=1), now, page_size=2)
                q = f.AuditListQuery(session, project, uuid.uuid4(), search)
                context = service.list_with_actor(q)
                assert context.actor_id == actor and context.project_id == project
                codec = AuditListCursorCodec(b"k" * 32)
                args = dict(session_token=session, actor_id=context.actor_id, project_id=context.project_id, search=search)
                cursor = codec.encode(**args, position=context.page.next_position)
                added = append(project)  # normal new event outside the signed first-page window
                before = tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                moving = replace(search, start_at=search.start_at + timedelta(seconds=1), end_at=search.end_at + timedelta(seconds=1))
                second_search = codec.decode_saved_window(cursor, **(args | dict(search=moving)))
                second_context = service.list_resolved(replace(q,search=moving),AuditCursorSearchResolver(codec,cursor,dates_omitted=True)) if resolved else service.list_with_actor(replace(q,search=second_search))
                assert second_context.search == second_search
                second = second_context.page
                ids = [v.audit_event_id for v in context.page.items + second.items]
                assert len(ids) == len(set(ids)) == 3 and set(ids) == set(local) and added not in ids
                assert second_search.start_at == search.start_at and second_search.end_at == search.end_at
                for changed in (dict(search=moving), dict(session_token=admin_session), dict(actor_id=admin_actor), dict(project_id=None), dict(project_id=uuid.uuid4()), dict(search=replace(search, page_size=3)), dict(search=replace(search, action="OTHER"))):
                    try:
                        codec.decode(cursor, **(args | changed))
                    except ApplicationError as exc:
                        assert exc.spec.code == "REQUEST_MALFORMED"
                    else:
                        raise AssertionError("cursor binding bypass")
                aq = replace(q, session_token=admin_session, project_id=None)
                ac = service.list_with_actor(aq)
                assert ac.actor_id == admin_actor and ac.project_id is None
                aa = dict(session_token=admin_session, actor_id=admin_actor, project_id=None, search=search)
                at = codec.encode(**aa, position=ac.page.next_position)
                ap = (service.list_resolved(aq,AuditCursorSearchResolver(codec,at)) if resolved else service.list_with_actor(replace(aq,search=codec.decode(at,**aa)))).page
                assert {v.audit_event_id for v in ac.page.items + ap.items} == set(deployed)
                if http:
                    from fastapi.testclient import TestClient
                    from plm_assistant.entrypoints.api import create_app
                    from plm_assistant.modules.audit.api.read_events import create_audit_read_router
                    from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
                    app=create_app(audit_read_router=create_audit_read_router(reads=service,origins=LoginOriginPolicy(["http://localhost"]),cursors=codec,clock=lambda:now))
                    path=f"/api/v1/projects/{project}/audit-events"
                    headers={"Cookie":"plm_session="+session.hex()}
                    ah={"Cookie":"plm_session="+admin_session.hex()}
                    with TestClient(app,base_url="http://localhost") as client:
                        first=client.get(path,headers=headers,params={"page_size":2})
                        assert first.status_code==200 and first.headers["Cache-Control"]=="no-store"
                        body=first.json()["data"]
                        second=client.get(path,headers=headers,params={"page_size":2,"cursor":body["next_cursor"]})
                        assert second.status_code==200
                        records=body["items"]+second.json()["data"]["items"]
                        assert len(records)==3 and {v["audit_event_id"] for v in records}=={str(v) for v in local}
                        assert client.get(path+"/"+str(local[0]),headers=headers).status_code==200
                        assert client.get(path+"/"+str(deployed[0]),headers=headers).status_code==404
                        assert client.get(path,headers=ah).status_code==404
                        assert client.get("/api/v1/admin/audit-events",headers=headers).status_code==401
                        assert client.get("/api/v1/admin/audit-events",headers=ah).status_code==200
                        assert client.get("/api/v1/admin/audit-events/"+str(deployed[0]),headers=ah).status_code==200
                        assert client.get("/api/v1/admin/audit-events/"+str(local[0]),headers=ah).status_code==404
                        assert client.get(path,headers=headers,params={"page_size":3,"cursor":body["next_cursor"]}).status_code==400
                        assert client.get(path,headers=headers,params={"action":"SYNTHETIC_CURSOR_EVENT"}).status_code==200
                        assert client.get(path,headers=headers,params={"action":"OTHER"}).json()["data"]["items"]==[]
                        assert client.get(path,headers=headers,params={"start_at":search.start_at.isoformat(),"end_at":search.end_at.isoformat()}).status_code==200
                        service._guard.enabled=False
                        assert client.get(path,headers=headers).status_code==403
                        assert client.get("/api/v1/admin/audit-events",headers=ah).status_code==403
                        service._guard.enabled=True
                        assert "actor_hint_digest" not in first.text and session.hex() not in first.text
                if platform_check is not None:
                    platform_check(url=url,session=session,admin_session=admin_session,project=project,local=local+[added],deployed=deployed,guard=service._guard)
                # Valid integrity is not current authorization: each page rechecks actual facts.
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s", (actor,))
                decoded = codec.decode(cursor, **args)
                try:
                    service.list_resolved(q,AuditCursorSearchResolver(codec,cursor)) if resolved else service.list_with_actor(replace(q,search=decoded))
                except f.AuthorizedAuditReadError as exc:
                    assert exc.code == "RESOURCE_NOT_FOUND"
                else:
                    raise AssertionError("cursor bypassed suspended membership")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s", (actor,))
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1 WHERE user_id=%s", (actor,))
                try:
                    service.list_resolved(q,AuditCursorSearchResolver(codec,cursor)) if resolved else service.list_with_actor(replace(q,search=decoded))
                except f.AuthorizedAuditReadError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("cursor bypassed revoked Session")
                if http:
                    with TestClient(app,base_url="http://localhost") as client:
                        assert client.get(path,headers=headers,params={"page_size":2,"cursor":body["next_cursor"]}).status_code==401
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")) == before
            label="AUD-02-A03-P02 opt-in HTTP" if http else "AUD-02-A03-P01 same-UOW resolution" if resolved else "AUD-02-A02"
            pending="no production key provisioning/MVCC snapshot" if http else "no HTTP/key provisioning/MVCC snapshot"
            print(label+" PASS: signed actual-actor/scope/session/query/window keyset, PROJECT/DEPLOYMENT pages, new event outside saved window, current membership/session revocation, reads unchanged; synthetic License, "+pending)
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
