"""Disposable PostgreSQL verification for member lifecycle commands."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch as mock_patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    create_production_platform_app, create_production_platform_write_app,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.change_member_state import create_project_member_state_router
from plm_assistant.modules.auth.infrastructure.project_member_patch_access import SqlAlchemyProjectMemberPatchAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.change_member_state import (
    ChangeProjectMemberState, ProjectMemberStateError, ProjectMemberStateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_state_repository import SqlAlchemyProjectMemberStateRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    def __init__(self):
        self.valid = True

    def require_valid(self, **_):
        if not self.valid:
            raise RuntimeLicenseError("EXPIRED")


class HttpSessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"p" * 32 or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectMemberStateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj02a04_" + uuid.uuid4().hex[:12]
    token1, token2 = b"p" * 32, b"q" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0016")
            with connect(name) as existing_db:
                user(existing_db, "Synthetic Existing Before Upgrade")
            command.upgrade(migration, "head")
            with connect(name) as upgraded:
                assert upgraded.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 1
                assert upgraded.execute("SELECT count(*) FROM plm.prj_member_state_results").fetchone()[0] == 0
            command.downgrade(migration, "20260925_0016")
            command.upgrade(migration, "head")
            command.check(migration)
            with connect(name) as db:
                manager = user(db, "Synthetic Manager", token1)
                manager2 = user(db, "Synthetic Manager Two", token2)
                target = user(db, "Synthetic Target")
                future = user(db, "Synthetic Future")
                outsider = user(db, "Synthetic Outsider")
                replay_target = user(db, "Synthetic Replay Target")
                concurrent_target = user(db, "Synthetic Concurrent Target")
                audit_target = user(db, "Synthetic Audit Target")
                http_target = user(db, "Synthetic HTTP Target")
                platform_target = user(db, "Synthetic Platform Target")
                platform_write_target = user(db, "Synthetic Platform Write Target")
                p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p1,)).fetchone()[0]
                d3 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','Other') RETURNING department_id", (p2,)).fetchone()[0]
                pm1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                pm2 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager2, d1)).fetchone()[0]
                member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, target, d1)).fetchone()[0]
                future_time = datetime.now(timezone.utc) + timedelta(days=1)
                future_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,effective_at) VALUES (%s,%s,%s,'CUSTOMER_MEMBER',%s) RETURNING project_member_id", (p1, future, d1, future_time)).fetchone()[0]
                foreign_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p2, outsider, d3)).fetchone()[0]
                replay_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, replay_target, d1)).fetchone()[0]
                concurrent_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, concurrent_target, d1)).fetchone()[0]
                audit_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, audit_target, d1)).fetchone()[0]
                http_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, http_target, d1)).fetchone()[0]
                platform_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, platform_target, d1)).fetchone()[0]
                platform_write_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, platform_write_target, d1)).fetchone()[0]
            runtime = create_database_runtime(url)
            try:
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberPatchAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectMemberStateRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectMemberStateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))
                idempotent = ProjectMemberStateService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                )

                def action(which, *, member_id=member, version=0, target_token=token1,
                           csrf=CSRF, project=p1, client=service):
                    return getattr(client, which)(ChangeProjectMemberState(
                        target_token, csrf, uuid.uuid4(), project, member_id, version,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: action("suspend", csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: action("suspend", member_id=foreign_member))
                guard.valid = False
                try:
                    action("suspend")
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                suspended = action("suspend")
                assert (suspended.state, suspended.etag, suspended.ended_at) == ("SUSPENDED", '"v1"', None)
                denied("CONFLICT_VERSION", lambda: action("resume"))
                denied("CONFLICT_STATE", lambda: action("suspend", version=1))
                resumed = action("resume", version=1)
                assert (resumed.state, resumed.etag) == ("ACTIVE", '"v2"')
                denied("CONFLICT_STATE", lambda: action("resume", version=2))
                failed = ProjectMemberStateService(**kwargs, audit=FailedAudit())
                try:
                    action("remove", version=2, client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (member,)).fetchone() == ("ACTIVE", 2)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (member,)).fetchone()[0] == 2
                removed = action("remove", version=2)
                assert (removed.state, removed.etag) == ("REMOVED", '"v3"')
                assert removed.ended_at is not None and removed.ended_at >= removed.effective_at
                denied("CONFLICT_STATE", lambda: action("resume", version=3))
                future_removed = action("remove", member_id=future_member)
                assert future_removed.ended_at == future_removed.effective_at
                replay_command = ChangeProjectMemberState(
                    token1, CSRF, uuid.uuid4(), p1, replay_member, 0,
                )
                suspended_first = idempotent.suspend_idempotent(
                    replay_command, idempotency_key="member-suspend-replay-001",
                )
                resumed_first = idempotent.resume_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 1),
                    idempotency_key="member-resume-replay-001",
                )
                removed_first = idempotent.remove_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 2),
                    idempotency_key="member-remove-replay-001",
                )
                assert (suspended_first.state, resumed_first.state, removed_first.state) == (
                    "SUSPENDED", "ACTIVE", "REMOVED",
                )
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET username_display='Synthetic Renamed' WHERE user_id=%s", (replay_target,))
                    db.execute("UPDATE plm.prj_departments SET name='Renamed Department' WHERE department_id=%s", (d1,))
                assert idempotent.suspend_idempotent(
                    replay_command, idempotency_key="member-suspend-replay-001",
                ) == suspended_first
                assert idempotent.resume_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 1),
                    idempotency_key="member-resume-replay-001",
                ) == resumed_first
                assert idempotent.remove_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 2),
                    idempotency_key="member-remove-replay-001",
                ) == removed_first
                assert suspended_first.user_display_name == "Synthetic Replay Target"
                assert suspended_first.department_name == "First"
                denied("CONFLICT_IDEMPOTENCY", lambda: idempotent.suspend_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 1),
                    idempotency_key="member-suspend-replay-001",
                ))
                concurrent_command = ChangeProjectMemberState(
                    token1, CSRF, uuid.uuid4(), p1, concurrent_member, 0,
                )
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(
                        lambda _: idempotent.suspend_idempotent(
                            concurrent_command, idempotency_key="member-suspend-concurrent-001",
                        ), range(2),
                    ))
                assert outcomes[0] == outcomes[1]
                for method, version, key in (
                    ("resume_idempotent", 1, "member-resume-concurrent-001"),
                    ("remove_idempotent", 2, "member-remove-concurrent-001"),
                ):
                    concurrent_next = ChangeProjectMemberState(
                        token1, CSRF, uuid.uuid4(), p1, concurrent_member, version,
                    )
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        outcomes = list(pool.map(
                            lambda _: getattr(idempotent, method)(
                                concurrent_next, idempotency_key=key,
                            ), range(2),
                        ))
                    assert outcomes[0] == outcomes[1]
                failed_idempotent = ProjectMemberStateService(
                    **kwargs, audit=FailedAudit(), receipts=SqlAlchemyIdempotencyReceipts(),
                )
                rollback_command = ChangeProjectMemberState(
                    token1, CSRF, uuid.uuid4(), p1, audit_member, 0,
                )
                try:
                    failed_idempotent.remove_idempotent(
                        rollback_command, idempotency_key="member-remove-audit-rollback-001",
                    )
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("idempotent Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (audit_member,)).fetchone() == ("ACTIVE", 0)
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PROJECT_MEMBER_REMOVE' AND key_digest=%s", (hashlib.sha256(b"member-remove-audit-rollback-001").digest(),)).fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (replay_member,)).fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (concurrent_member,)).fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.prj_member_state_results WHERE member_id=%s", (replay_member,)).fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.prj_member_state_results WHERE member_id=%s", (concurrent_member,)).fetchone()[0] == 3
                    try:
                        db.execute("UPDATE plm.prj_member_state_results SET state='ACTIVE' WHERE member_id=%s", (replay_member,))
                    except psycopg.errors.RaiseException:
                        pass
                    else:
                        raise AssertionError("state snapshot unexpectedly mutable")
                router = create_project_member_state_router(
                    sessions=HttpSessions(), members=idempotent,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                with TestClient(create_app(project_member_state_router=router),
                                base_url="http://localhost") as client:
                    base_path = f"/api/v1/projects/{p1}/members/{http_member}"
                    headers = {"origin": "http://localhost",
                               "cookie": "plm_session=" + token1.hex(),
                               "x-csrf-token": CSRF.hex()}
                    results = {}
                    for operation, version, state in (
                        ("suspend", 0, "SUSPENDED"),
                        ("resume", 1, "ACTIVE"),
                        ("remove", 2, "REMOVED"),
                    ):
                        command_headers = {**headers, "if-match": f'"v{version}"',
                                           "idempotency-key": f"member-http-{operation}-key-001"}
                        first_http = client.post(base_path + ":" + operation,
                                                 headers=command_headers)
                        replay_http = client.post(base_path + ":" + operation,
                                                  headers=command_headers)
                        assert first_http.status_code == replay_http.status_code == 200, (first_http.text, replay_http.text)
                        assert first_http.json()["data"] == replay_http.json()["data"]
                        assert first_http.json()["data"]["state"] == state
                        assert first_http.headers["etag"] == f'"v{version + 1}"'
                        results[operation] = first_http.json()["data"]
                    assert client.post(base_path + ":suspend", headers={
                        **headers, "if-match": '"v0"',
                        "idempotency-key": "member-http-suspend-key-001",
                    }).json()["data"] == results["suspend"]
                    assert client.post(base_path + ":remove", headers={
                        **headers, "if-match": '"v1"',
                        "idempotency-key": "member-http-remove-key-001",
                    }).status_code == 409
                    assert client.post(f"/api/v1/projects/{p2}/members/{http_member}:suspend", headers={
                        **headers, "if-match": '"v0"',
                        "idempotency-key": "member-http-cross-project-001",
                    }).status_code == 404
                    guard.valid = False
                    assert client.post(base_path + ":remove", headers={
                        **headers, "if-match": '"v2"',
                        "idempotency-key": "member-http-remove-key-001",
                    }).status_code == 403
                    guard.valid = True
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (http_member,)).fetchone() == ("REMOVED", 3)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (http_member,)).fetchone()[0] == 3
                settings = BootstrapSettings(
                    data_root=Path.cwd(), trusted_origins=("http://localhost",),
                )
                with mock_patch("plm_assistant.entrypoints.production_login.read_database_url",
                                return_value=url), mock_patch(
                                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                                return_value=SimpleNamespace(guard=guard)), mock_patch(
                                "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                                return_value=SecretListCursorCodec(b"q" * 32)), mock_patch(
                                "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                                return_value=MemberListCursorCodec(b"m" * 32)), mock_patch(
                                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                return_value=Mock()):
                    for factory, target_member in (
                        (create_production_platform_app, platform_member),
                        (create_production_platform_write_app, platform_write_member),
                    ):
                        platform = factory(settings)
                        with TestClient(platform, base_url="http://localhost") as client:
                            path = f"/api/v1/projects/{p1}/members/{target_member}"
                            platform_headers = {
                                "origin": "http://localhost",
                                "cookie": "plm_session=" + token1.hex(),
                                "x-csrf-token": CSRF.hex(),
                            }
                            for operation, version, state in (
                                ("suspend", 0, "SUSPENDED"),
                                ("resume", 1, "ACTIVE"),
                                ("remove", 2, "REMOVED"),
                            ):
                                request_headers = {
                                    **platform_headers, "if-match": f'"v{version}"',
                                    "idempotency-key": f"platform-{target_member}-{operation}",
                                }
                                first = client.post(path + ":" + operation, headers=request_headers)
                                replay = client.post(path + ":" + operation, headers=request_headers)
                                assert first.status_code == replay.status_code == 200, (first.text, replay.text)
                                assert first.json()["data"] == replay.json()["data"]
                                assert first.json()["data"]["state"] == state
                            guard.valid = False
                            assert client.post(path + ":remove", headers={
                                **platform_headers, "if-match": '"v2"',
                                "idempotency-key": f"platform-{target_member}-remove",
                            }).status_code == 403
                            guard.valid = True
                        with connect(name) as db:
                            assert db.execute("SELECT state,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (target_member,)).fetchone() == ("REMOVED", 3)
                            assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (target_member,)).fetchone()[0] == 3
                    with mock_patch("plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                                    side_effect=RuntimeError("synthetic missing member key")):
                        try:
                            create_production_platform_app(settings)
                        except Exception as exc:
                            assert str(exc) == "production login unavailable"
                        else:
                            raise AssertionError("missing trust source did not fail closed")
                # One manager can leave while another remains; the last one cannot.
                first_manager = action("suspend", member_id=pm2)
                assert first_manager.state == "SUSPENDED"
                denied("PROJECT_ROLE_INVALID", lambda: action("suspend", member_id=pm1))
                denied("PROJECT_ROLE_INVALID", lambda: action("remove", member_id=pm1))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (d2,))
                    db.execute("UPDATE plm.prj_project_members SET department_id=%s WHERE project_member_id=%s", (d2, pm2))
                denied("PROJECT_ROLE_INVALID", lambda: action("resume", member_id=pm2, version=1))
                removed_suspended = action("remove", member_id=pm2, version=1)
                assert removed_suspended.state == "REMOVED" and removed_suspended.ended_at is not None
                denied("CONFLICT_STATE", lambda: action("resume", member_id=pm2, version=2))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: action("remove", member_id=pm2, version=1))
                assert idempotent.remove_idempotent(
                    ChangeProjectMemberState(token1, CSRF, uuid.uuid4(), p1, replay_member, 2),
                    idempotency_key="member-remove-replay-001",
                ) == removed_first
                try:
                    command.downgrade(migration, "20260925_0016")
                except RuntimeError as exc:
                    assert "member state results exist" in str(exc)
                else:
                    raise AssertionError("nonempty state result downgrade should fail")
                with connect(name) as db:
                    actions = db.execute("SELECT action,before_state,after_state FROM plm.aud_events WHERE target_object_id=%s ORDER BY occurred_at,audit_event_id", (member,)).fetchall()
                    assert actions == [
                        ("PROJECT_MEMBER_SUSPENDED", "ACTIVE", "SUSPENDED"),
                        ("PROJECT_MEMBER_RESUMED", "SUSPENDED", "ACTIVE"),
                        ("PROJECT_MEMBER_REMOVED", "ACTIVE", "REMOVED"),
                    ], actions
                print("PASS: empty/existing-data migration, 3 state HTTP and Windows explicit platform replay/security, concurrent one-write, snapshots, rollback and downgrade guard")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
