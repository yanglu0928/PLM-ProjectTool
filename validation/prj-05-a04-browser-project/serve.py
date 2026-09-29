"""Owned Windows browser/PG fixture for read-only Project UI verification."""

from __future__ import annotations

import ctypes
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import uvicorn
import httpx
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints import production_login as production
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer


ROOT = Path(__file__).resolve().parents[2]
spec = spec_from_file_location("_owned_source", ROOT / "validation/aut-03-a07-p03-production-login/verify.py")
source = module_from_spec(spec)
spec.loader.exec_module(source)


class SyntheticGuard:
    def require_valid(self, *, trace_id):
        assert isinstance(trace_id, uuid.UUID)
        return object()


def reserve_port():
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def insert_user(db, name: str, password_hash, algorithm_id: str):
    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                      "VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials "
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
        (user, password_hash, algorithm_id, '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' "
               "WHERE user_id=%s", (credential, user))
    return user


def verify_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    with httpx.Client(base_url=origin, timeout=20) as member:
        assert member.get("/api/v1/projects").status_code == 401
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        listing = member.get("/api/v1/projects")
        assert listing.status_code == 200, listing.text
        data = listing.json()["data"]
        assert data["next_cursor"] is None and data["has_more"] is False
        assert len(data["items"]) == 1 and data["items"][0]["project_id"] == str(owned)
        detail = member.get(f"/api/v1/projects/{owned}")
        assert detail.status_code == 200 and detail.headers["ETag"] == detail.json()["data"]["etag"]
        assert detail.json()["data"]["project_id"] == str(owned)
        rejected = member.get(f"/api/v1/projects/{foreign}")
        assert rejected.status_code == 404 and rejected.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert "Synthetic Foreign Project" not in rejected.text
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200 and login.json()["data"]["deployment_role"] == "DEPLOYMENT_ADMIN"
        listing = admin.get("/api/v1/projects")
        assert listing.status_code == 200 and listing.json()["data"]["items"] == []
        rejected = admin.get(f"/api/v1/projects/{owned}")
        assert rejected.status_code == 404 and rejected.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    print("PROJECT_BROWSER_HTTP PASS: no Cookie401, member list/detail200, foreign404, admin empty/404", flush=True)


def verify_create_http(origin: str, manager: uuid.UUID) -> uuid.UUID:
    body = {"code": "CREATE-P04", "name": "Synthetic Created Project",
            "initial_manager_user_id": str(manager)}
    key = "synthetic-project-create-p04"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        denied = anonymous.post("/api/v1/projects", headers={"Origin": origin,
            "X-CSRF-Token": "a" * 64, "Idempotency-Key": key}, json=body)
        assert denied.status_code == 401, denied.text
    with httpx.Client(base_url=origin, timeout=20) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        denied = member.post("/api/v1/projects", headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "Idempotency-Key": key}, json=body)
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200 and login.json()["data"]["deployment_role"] == "DEPLOYMENT_ADMIN"
        users = admin.get("/api/v1/admin/users", params={"page_size": 50})
        assert users.status_code == 200, users.text
        candidate = next((item for item in users.json()["data"]["items"]
                          if item["user_id"] == str(manager)), None)
        assert candidate is not None and candidate["account_state"] == "ENABLED"
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "Idempotency-Key": key}
        first = admin.post("/api/v1/projects", headers=headers, json=body)
        replay = admin.post("/api/v1/projects", headers=headers, json=body)
        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
        assert first.json()["data"] == replay.json()["data"]
        created = uuid.UUID(first.json()["data"]["project_id"])
        assert first.headers["ETag"] == '"v0"'
        assert first.headers["Location"] == f"/api/v1/projects/{created}"
        conflicting = admin.post("/api/v1/projects", headers=headers,
                                 json={**body, "name": "Changed"})
        assert conflicting.status_code == 409 and conflicting.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY"
        print("PROJECT_CREATE_HTTP PASS: anonymous401, member404, admin candidates200/create201/replay201/conflict409", flush=True)
        return created


def verify_member_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    with httpx.Client(base_url=origin, timeout=20) as viewer:
        login = viewer.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Viewer", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        assert viewer.get(f"/api/v1/projects/{owned}").status_code == 200
        denied = viewer.get(f"/api/v1/projects/{owned}/members?page_size=50")
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        assert admin.get(f"/api/v1/projects/{owned}/members?page_size=50").status_code == 404
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        first = manager.get(f"/api/v1/projects/{owned}/members?page_size=50")
        assert first.status_code == 200, first.text
        page = first.json()["data"]
        assert len(page["items"]) == 50 and page["has_more"] is True and page["next_cursor"]
        second = manager.get(f"/api/v1/projects/{owned}/members", params={"page_size": 50, "cursor": page["next_cursor"]})
        assert second.status_code == 200, second.text
        tail = second.json()["data"]
        assert len(tail["items"]) == 2 and tail["has_more"] is False and tail["next_cursor"] is None
        items = page["items"] + tail["items"]
        assert len({item["member_id"] for item in items}) == 52
        assert sum(item["state"] == "REMOVED" for item in items) == 1
        assert not any("password_hash" in str(item) for item in items)
        assert manager.get(f"/api/v1/projects/{foreign}/members?page_size=50").status_code == 404
        wrong_size = manager.get(f"/api/v1/projects/{owned}/members",
            params={"page_size": 20, "cursor": page["next_cursor"]})
        assert wrong_size.status_code == 400, wrong_size.text
    print("PROJECT_MEMBER_BROWSER_HTTP PASS: viewer/admin404, manager50+2, removed history, foreign404, cursor binding400", flush=True)


def verify_member_create_http(origin: str, project: uuid.UUID, target: uuid.UUID,
                              department: uuid.UUID):
    route = f"/api/v1/projects/{project}/member-candidates:resolve"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.post(route, headers={"Origin": origin},
                              json={"username": "Synthetic Candidate Target"}).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        csrf = login.json()["data"]["csrf_token"]
        headers = {"Origin": origin, "X-CSRF-Token": csrf}
        exact = manager.post(route, headers=headers, json={"username": "Synthetic Candidate Target"})
        assert exact.status_code == 200 and exact.json()["data"]["candidate"]["user_id"] == str(target), exact.text
        missing = manager.post(route, headers=headers, json={"username": "Synthetic Nobody"})
        assert missing.status_code == 200 and missing.json()["data"] == {"candidate": None}
        page = manager.get(f"/api/v1/projects/{project}/departments", params={"page_size": 50})
        assert page.status_code == 200, page.text
        active = [item for item in page.json()["data"]["items"] if item["state"] == "ACTIVE"]
        assert len(active) == 1 and active[0]["department_id"] == str(department)
        body = {"user_id": str(target), "role": "IMPLEMENTATION_MEMBER", "department_id": str(department)}
        create_headers = {**headers, "Idempotency-Key": "synthetic-member-create-a05"}
        first = manager.post(f"/api/v1/projects/{project}/members", headers=create_headers, json=body)
        replay = manager.post(f"/api/v1/projects/{project}/members", headers=create_headers, json=body)
        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
        assert first.json()["data"] == replay.json()["data"]
        conflict = manager.post(f"/api/v1/projects/{project}/members", headers=create_headers,
                                json={**body, "role": "CUSTOMER_MEMBER"})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY"
    print("PROJECT_MEMBER_CREATE_HTTP PASS: anonymous401, exact/miss, ACTIVE department, create/replay201/conflict409", flush=True)


def verify_member_patch_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                             target: uuid.UUID, department: uuid.UUID):
    route = f"/api/v1/projects/{project}/members/{target}"
    body = {"role": "CUSTOMER_MEMBER", "department_id": str(department)}
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.patch(route, headers={"Origin": origin, "If-Match": '"v0"'}, json=body).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.patch(route, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "If-Match": '"v0"'}, json=body)
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        csrf = login.json()["data"]["csrf_token"]
        headers = {"Origin": origin, "X-CSRF-Token": csrf, "If-Match": '"v0"'}
        assert manager.patch(route, headers={"Origin": origin, "If-Match": '"v0"'}, json=body).status_code == 403
        foreign_result = manager.patch(f"/api/v1/projects/{foreign}/members/{target}", headers=headers, json=body)
        assert foreign_result.status_code == 404, foreign_result.text
        first = manager.patch(route, headers=headers, json=body)
        assert first.status_code == 200 and first.headers["ETag"] == '"v1"', first.text
        assert first.json()["data"]["role"] == "CUSTOMER_MEMBER"
        assert first.json()["data"]["department"]["department_id"] == str(department)
        stale = manager.patch(route, headers=headers, json=body)
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "CONFLICT_VERSION", stale.text
        no_op = manager.patch(route, headers={**headers, "If-Match": '"v1"'}, json=body)
        assert no_op.status_code == 200 and no_op.headers["ETag"] == '"v1"', no_op.text
    print("PROJECT_MEMBER_PATCH_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/change200-v1/stale409/no-op200-v1", flush=True)


def verify_member_state_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                             target: uuid.UUID):
    route = f"/api/v1/projects/{project}/members/{target}"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.post(route + ":suspend", headers={"Origin": origin,
            "If-Match": '"v0"', "Idempotency-Key": "synthetic-state-suspend-0001"}).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.post(route + ":suspend", headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "If-Match": '"v0"',
            "Idempotency-Key": "synthetic-state-suspend-0001"})
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        csrf = login.json()["data"]["csrf_token"]
        headers = {"Origin": origin, "X-CSRF-Token": csrf,
                   "If-Match": '"v0"', "Idempotency-Key": "synthetic-state-suspend-0001"}
        assert manager.post(route + ":suspend", headers={"Origin": origin,
            "If-Match": '"v0"', "Idempotency-Key": headers["Idempotency-Key"]}).status_code == 403
        denied = manager.post(f"/api/v1/projects/{foreign}/members/{target}:suspend", headers=headers)
        assert denied.status_code == 404, denied.text
        first = manager.post(route + ":suspend", headers=headers)
        replay = manager.post(route + ":suspend", headers=headers)
        assert first.status_code == replay.status_code == 200, (first.text, replay.text)
        assert first.headers["ETag"] == replay.headers["ETag"] == '"v1"'
        assert first.json()["data"] == replay.json()["data"]
        assert first.json()["data"]["state"] == "SUSPENDED"
        conflict = manager.post(route + ":suspend", headers={**headers, "If-Match": '"v1"'})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY", conflict.text
        resumed = manager.post(route + ":resume", headers={**headers,
            "If-Match": '"v1"', "Idempotency-Key": "synthetic-state-resume-0001"})
        assert resumed.status_code == 200 and resumed.headers["ETag"] == '"v2"', resumed.text
        assert resumed.json()["data"]["state"] == "ACTIVE"
        removed = manager.post(route + ":remove", headers={**headers,
            "If-Match": '"v2"', "Idempotency-Key": "synthetic-state-remove-0001"})
        assert removed.status_code == 200 and removed.headers["ETag"] == '"v3"', removed.text
        assert removed.json()["data"]["state"] == "REMOVED" and removed.json()["data"]["ended_at"]
        history = manager.get(f"/api/v1/projects/{project}/members", params={"page_size": 50})
        assert history.status_code == 200, history.text
        target_row = next(item for item in history.json()["data"]["items"] if item["member_id"] == str(target))
        assert target_row["state"] == "REMOVED" and target_row["etag"] == '"v3"'
    print("PROJECT_MEMBER_STATE_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/suspend-replay-v1/key-conflict409/resume-v2/remove-v3/history", flush=True)


def verify_department_history_http(origin: str, project: uuid.UUID, foreign: uuid.UUID):
    route = f"/api/v1/projects/{project}/departments"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.get(route, params={"page_size": 50}).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        assert admin.get(route, params={"page_size": 50}).status_code == 404
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        assert manager.get(f"/api/v1/projects/{foreign}/departments", params={"page_size": 50}).status_code == 404
        first = manager.get(route, params={"page_size": 50})
        assert first.status_code == 200, first.text
        page = first.json()["data"]
        assert len(page["items"]) == 50 and page["has_more"] and page["next_cursor"]
        second = manager.get(route, params={"page_size": 50, "cursor": page["next_cursor"]})
        assert second.status_code == 200, second.text
        last = second.json()["data"]
        assert len(last["items"]) == 2 and not last["has_more"] and last["next_cursor"] is None
        rows = page["items"] + last["items"]
        assert len({item["department_id"] for item in rows}) == 52
        assert sum(item["state"] == "INACTIVE" for item in rows) == 1
        assert next(item for item in rows if item["code"] == "OLD")["state"] == "INACTIVE"
    print("PROJECT_DEPARTMENT_HISTORY_HTTP PASS: anonymous401/admin404/foreign404/50+2/one inactive", flush=True)


def verify_department_create_http(origin: str, project: uuid.UUID, foreign: uuid.UUID):
    route = f"/api/v1/projects/{project}/departments"
    body = {"code": "NEW", "name": "Synthetic Created Department"}
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.post(route, headers={"Origin": origin,
            "Idempotency-Key": "synthetic-department-create-0001"}, json=body).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.post(route, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"],
            "Idempotency-Key": "synthetic-department-create-0001"}, json=body)
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "Idempotency-Key": "synthetic-department-create-0001"}
        assert manager.post(route, headers={"Origin": origin,
            "Idempotency-Key": headers["Idempotency-Key"]}, json=body).status_code == 403
        denied = manager.post(f"/api/v1/projects/{foreign}/departments", headers=headers, json=body)
        assert denied.status_code == 404, denied.text
        first = manager.post(route, headers=headers, json=body)
        replay = manager.post(route, headers=headers, json=body)
        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
        assert first.headers["ETag"] == replay.headers["ETag"] == '"v0"'
        assert first.json()["data"] == replay.json()["data"]
        result = first.json()["data"]
        assert result["code"] == "NEW" and result["name"] == body["name"] and result["state"] == "ACTIVE"
        assert first.headers["Location"] == f"{route}/{result['department_id']}"
        conflict = manager.post(route, headers=headers, json={**body, "name": "Different"})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY", conflict.text
        history = manager.get(route, params={"page_size": 50})
        assert history.status_code == 200, history.text
        assert sum(item["code"] == "NEW" for item in history.json()["data"]["items"]) == 1
    print("PROJECT_DEPARTMENT_CREATE_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/201-replay-v0/key-conflict409/history", flush=True)


def verify_department_patch_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                                 department: uuid.UUID):
    route = f"/api/v1/projects/{project}/departments/{department}"
    body = {"code": "NEW", "name": "Synthetic Patched Department"}
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.patch(route, headers={"Origin": origin, "If-Match": '"v0"'}, json=body).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.patch(route, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "If-Match": '"v0"'}, json=body)
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "If-Match": '"v0"'}
        assert manager.patch(route, headers={"Origin": origin, "If-Match": '"v0"'}, json=body).status_code == 403
        denied = manager.patch(f"/api/v1/projects/{foreign}/departments/{department}",
            headers=headers, json=body)
        assert denied.status_code == 404, denied.text
        missing = manager.patch(route, headers={"Origin": origin,
            "X-CSRF-Token": headers["X-CSRF-Token"]}, json=body)
        assert missing.status_code == 428, missing.text
        first = manager.patch(route, headers=headers, json=body)
        assert first.status_code == 200 and first.headers["ETag"] == '"v1"', first.text
        result = first.json()["data"]
        assert result["department_id"] == str(department) and result["code"] == "NEW"
        assert result["name"] == body["name"] and result["state"] == "ACTIVE"
        stale = manager.patch(route, headers=headers, json=body)
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "CONFLICT_VERSION", stale.text
        same = manager.patch(route, headers={**headers, "If-Match": '"v1"'}, json=body)
        assert same.status_code == 200 and same.headers["ETag"] == '"v1"', same.text
        history = manager.get(f"/api/v1/projects/{project}/departments", params={"page_size": 50})
        assert history.status_code == 200, history.text
        assert any(item["department_id"] == str(department) and item["code"] == "NEW"
                   and item["etag"] == '"v1"' for item in history.json()["data"]["items"])
    print("PROJECT_DEPARTMENT_PATCH_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/IfMatch428/v1/stale409/noop-v1/history", flush=True)


def verify_department_deactivate_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                                      occupied: uuid.UUID, free: uuid.UUID):
    route = f"/api/v1/projects/{project}/departments/{free}:deactivate"
    key = "synthetic-department-deactivate-0001"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.post(route, headers={"Origin": origin, "If-Match": '"v0"',
            "Idempotency-Key": key}).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.post(route, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"], "If-Match": '"v0"',
            "Idempotency-Key": key})
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "If-Match": '"v0"', "Idempotency-Key": key}
        assert manager.post(route, headers={"Origin": origin, "If-Match": '"v0"',
            "Idempotency-Key": key}).status_code == 403
        denied = manager.post(f"/api/v1/projects/{foreign}/departments/{free}:deactivate",
            headers=headers)
        assert denied.status_code == 404, denied.text
        missing = manager.post(route, headers={"Origin": origin,
            "X-CSRF-Token": headers["X-CSRF-Token"], "Idempotency-Key": key})
        assert missing.status_code == 428, missing.text
        occupied_route = f"/api/v1/projects/{project}/departments/{occupied}:deactivate"
        in_use = manager.post(occupied_route, headers={**headers,
            "Idempotency-Key": "synthetic-department-in-use-0001"})
        assert in_use.status_code == 409 and in_use.json()["error"]["code"] == "PROJECT_DEPARTMENT_IN_USE", in_use.text
        first = manager.post(route, headers=headers)
        replay = manager.post(route, headers=headers)
        assert first.status_code == replay.status_code == 200, (first.text, replay.text)
        assert first.headers["ETag"] == replay.headers["ETag"] == '"v1"'
        assert first.json()["data"] == replay.json()["data"]
        result = first.json()["data"]
        assert result["department_id"] == str(free) and result["code"] == "FREE"
        assert result["state"] == "INACTIVE" and result["etag"] == '"v1"'
        conflict = manager.post(route, headers={**headers, "If-Match": '"v1"'})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY", conflict.text
        history = manager.get(f"/api/v1/projects/{project}/departments", params={"page_size": 50})
        assert history.status_code == 200, history.text
        assert any(item["department_id"] == str(free) and item["state"] == "INACTIVE"
                   and item["etag"] == '"v1"' for item in history.json()["data"]["items"])
    print("PROJECT_DEPARTMENT_DEACTIVATE_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/IfMatch428/in-use409/200-replay/key-conflict409/history", flush=True)


def main():
    suffix = uuid.uuid4().hex[:12]
    dbname = role = "prj05a04_" + suffix
    target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    role_secret = uuid.uuid4().hex + uuid.uuid4().hex
    port = reserve_port()
    origin = f"http://127.0.0.1:{port}"
    proxy = server = thread = sock = None
    logs = StringIO()
    with source.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(role_secret)))
        try:
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier(role)))
            try:
                url = URL.create("postgresql+psycopg", username=role, password=role_secret,
                                 host=source.HOST, port=source.PORT, database=dbname)
                with source.connect(dbname) as db:
                    db.execute("CREATE EXTENSION IF NOT EXISTS vector")
                command.upgrade(source.create_migration_config(url), "head")
                clear = bytearray(b"synthetic-project-only-password")
                try:
                    with memoryview(clear) as view:
                        hashed = source.ScryptPasswordHasher().hash_password(view)
                finally:
                    clear[:] = b"\x00" * len(clear)
                with source.connect(dbname) as db:
                    member = insert_user(db, "Synthetic Project Member", hashed.password_hash, hashed.algorithm_id)
                    admin_user = insert_user(db, "Synthetic Project Admin", hashed.password_hash, hashed.algorithm_id)
                    create_mode = "--create-api-only" in sys.argv[1:] or "--create-browser" in sys.argv[1:]
                    state_mode = "--user-state-browser" in sys.argv[1:]
                    name_mode = "--user-name-browser" in sys.argv[1:]
                    member_create_mode = ("--member-create-browser" in sys.argv[1:]
                                          or "--member-create-api-only" in sys.argv[1:])
                    member_patch_mode = ("--member-patch-browser" in sys.argv[1:]
                                         or "--member-patch-api-only" in sys.argv[1:])
                    member_state_mode = ("--member-state-browser" in sys.argv[1:]
                                         or "--member-state-api-only" in sys.argv[1:])
                    department_history_mode = ("--department-history-browser" in sys.argv[1:]
                                               or "--department-history-api-only" in sys.argv[1:])
                    department_create_mode = ("--department-create-browser" in sys.argv[1:]
                                              or "--department-create-api-only" in sys.argv[1:])
                    department_patch_mode = ("--department-patch-browser" in sys.argv[1:]
                                             or "--department-patch-api-only" in sys.argv[1:])
                    department_deactivate_mode = ("--department-deactivate-browser" in sys.argv[1:]
                                                  or "--department-deactivate-api-only" in sys.argv[1:])
                    member_mode = ("--member-browser" in sys.argv[1:]
                                   or "--member-api-only" in sys.argv[1:])
                    if sum((create_mode, state_mode, name_mode, member_mode, member_create_mode,
                            member_patch_mode, member_state_mode, department_history_mode,
                            department_create_mode, department_patch_mode,
                            department_deactivate_mode)) > 1:
                        raise ValueError("Browser write modes must be exclusive")
                    manager = (insert_user(db, "Synthetic First Manager", hashed.password_hash, hashed.algorithm_id)
                               if create_mode else None)
                    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s", (admin_user,))
                    project = db.execute("INSERT INTO plm.prj_projects "
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('OWNED','owned','Synthetic Owned Project',%s) RETURNING project_id", (member,)).fetchone()[0]
                    foreign = db.execute("INSERT INTO plm.prj_projects "
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('FOREIGN','foreign','Synthetic Foreign Project',%s) RETURNING project_id", (admin_user,)).fetchone()[0]
                    department = db.execute("INSERT INTO plm.prj_departments "
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'D1','d1','Synthetic Department') RETURNING department_id", (project,)).fetchone()[0]
                    free_department = (db.execute("INSERT INTO plm.prj_departments "
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'FREE','free','Synthetic Free Department') RETURNING department_id",
                        (project,)).fetchone()[0] if department_deactivate_mode else None)
                    if department_history_mode:
                        for index in range(50):
                            code = f"H{index:02d}"
                            db.execute("INSERT INTO plm.prj_departments "
                                "(project_id,department_code,department_code_normalized,name) "
                                "VALUES (%s,%s,%s,%s)",
                                (project, code, code.lower(), f"Synthetic History Department {index:02d}"))
                        db.execute("INSERT INTO plm.prj_departments "
                            "(project_id,department_code,department_code_normalized,name,state) "
                            "VALUES (%s,'OLD','old','Synthetic Inactive Department','INACTIVE')", (project,))
                    target_user = (insert_user(db, "Synthetic Candidate Target", hashed.password_hash, hashed.algorithm_id)
                                   if member_create_mode else None)
                    patch_target = (insert_user(db, "Synthetic Patch Target", hashed.password_hash, hashed.algorithm_id)
                                    if member_patch_mode else None)
                    patch_department = None
                    patch_member = None
                    if member_patch_mode:
                        patch_department = db.execute("INSERT INTO plm.prj_departments "
                            "(project_id,department_code,department_code_normalized,name) "
                            "VALUES (%s,'D2','d2','Synthetic Patch Department') RETURNING department_id",
                            (project,)).fetchone()[0]
                    state_target = (insert_user(db, "Synthetic State Target", hashed.password_hash, hashed.algorithm_id)
                                    if member_state_mode else None)
                    state_member = None
                    if member_create_mode:
                        db.execute("INSERT INTO plm.prj_departments "
                            "(project_id,department_code,department_code_normalized,name,state) "
                            "VALUES (%s,'OLD','old','Synthetic Inactive Department','INACTIVE')", (project,))
                    db.execute("INSERT INTO plm.prj_project_members "
                        "(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, member, department))
                    if member_patch_mode:
                        patch_member = db.execute("INSERT INTO plm.prj_project_members "
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id",
                            (project, patch_target, department)).fetchone()[0]
                    if member_state_mode:
                        state_member = db.execute("INSERT INTO plm.prj_project_members "
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id",
                            (project, state_target, department)).fetchone()[0]
                    if member_mode:
                        viewer = insert_user(db, "Synthetic Project Viewer", hashed.password_hash, hashed.algorithm_id)
                        db.execute("INSERT INTO plm.prj_project_members "
                            "(project_id,user_id,department_id,project_role) "
                            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')", (project, viewer, department))
                        for index in range(50):
                            history_user = insert_user(db, f"Synthetic History {index:02d}",
                                                       hashed.password_hash, hashed.algorithm_id)
                            historical = db.execute("INSERT INTO plm.prj_project_members "
                                "(project_id,user_id,department_id,project_role) "
                                "VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id",
                                (project, history_user, department)).fetchone()[0]
                            if index == 49:
                                db.execute("UPDATE plm.prj_project_members SET state='REMOVED', "
                                    "ended_at=clock_timestamp(), lock_version=1 WHERE project_member_id=%s",
                                    (historical,))
                source.write_database_url(url.render_as_string(hide_password=False), target=target)
                try:
                    with tempfile.TemporaryDirectory(prefix="plm-project-browser-") as directory, ExitStack() as stack:
                        settings = BootstrapSettings(data_root=Path(directory), trusted_origins=(origin,))
                        prefix = "plm_assistant.entrypoints.production_login."
                        stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                                                  return_value=SimpleNamespace(guard=SyntheticGuard())))
                        for name, codec in (
                            ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                            ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                            ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                            ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                            ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                            ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                            ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                            ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                            ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                        ):
                            stack.enter_context(patch(prefix + name, return_value=codec))
                        if state_mode or name_mode:
                            stack.enter_context(patch(
                                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                return_value=object()))
                            stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                                return_value=HmacUploadTokenIssuer(
                                    provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                                    key_ref="synthetic-browser-upload-token")))
                        with redirect_stdout(logs):
                            factory = (production.create_production_platform_write_app if state_mode or name_mode
                                       else production.create_production_platform_app)
                            app = factory(settings, credential_target=target)
                        sock = socket.socket()
                        sock.bind(("127.0.0.1", 0))
                        sock.listen(128)
                        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
                        thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=False)
                        thread.start()
                        deadline = monotonic() + 15
                        while not server.started:
                            if not thread.is_alive() or monotonic() > deadline:
                                raise RuntimeError("Owned backend startup failed")
                            sleep(.05)
                        proxy = subprocess.Popen(["node", str(ROOT / "validation/aut-05-a04-network-login/start-proxy.mjs"),
                            str(port), str(sock.getsockname()[1])], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        ready = queue.Queue()
                        Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                        if ready.get(timeout=15) != "OWNED_PROXY_READY":
                            raise RuntimeError("Owned proxy startup failed")
                        print(f"PROJECT_BROWSER_READY {origin}/login OWNED={project} FOREIGN={foreign}"
                              + (f" MANAGER={manager}" if create_mode else "")
                              + (f" CANDIDATE={target_user}" if member_create_mode else "")
                              + (f" PATCH_TARGET={patch_member} PATCH_DEPARTMENT={patch_department}" if member_patch_mode else "")
                              + (f" DEACTIVATE_TARGET={free_department}" if department_deactivate_mode else "")
                              + (f" STATE_TARGET={state_member}" if member_state_mode else "")
                              + (f" USER_STATE_TARGET={member}" if state_mode else "")
                              + (f" USER_NAME_TARGET={member}" if name_mode else ""), flush=True)
                        if "--create-api-only" in sys.argv[1:]:
                            assert manager is not None
                            created = verify_create_http(origin, manager)
                        elif "--api-only" in sys.argv[1:]:
                            verify_http(origin, project, foreign)
                        elif "--member-api-only" in sys.argv[1:]:
                            verify_member_http(origin, project, foreign)
                        elif "--member-create-api-only" in sys.argv[1:]:
                            assert target_user is not None
                            verify_member_create_http(origin, project, target_user, department)
                        elif "--member-patch-api-only" in sys.argv[1:]:
                            assert patch_member is not None and patch_department is not None
                            verify_member_patch_http(origin, project, foreign, patch_member, patch_department)
                        elif "--member-state-api-only" in sys.argv[1:]:
                            assert state_member is not None
                            verify_member_state_http(origin, project, foreign, state_member)
                        elif "--department-history-api-only" in sys.argv[1:]:
                            verify_department_history_http(origin, project, foreign)
                        elif "--department-create-api-only" in sys.argv[1:]:
                            verify_department_create_http(origin, project, foreign)
                        elif "--department-patch-api-only" in sys.argv[1:]:
                            verify_department_patch_http(origin, project, foreign, department)
                        elif "--department-deactivate-api-only" in sys.argv[1:]:
                            assert free_department is not None
                            verify_department_deactivate_http(origin, project, foreign, department, free_department)
                        else:
                            actions = queue.Queue()
                            Thread(target=lambda: actions.put(sys.stdin.readline().strip()), daemon=True).start()
                            assert actions.get(timeout=900) == "VERIFY", "Browser verification not completed"
                        with source.connect(dbname) as db:
                            expected = 3 if create_mode else 2
                            assert db.execute("SELECT count(*) FROM plm.prj_projects").fetchone()[0] == expected
                            session_count = db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0]
                            if "--member-create-api-only" in sys.argv[1:]:
                                assert session_count == 1
                            elif "--api-only" in sys.argv[1:] or "--create-api-only" in sys.argv[1:]:
                                assert session_count == 2
                            elif "--member-api-only" in sys.argv[1:]:
                                assert session_count == 3
                            elif member_patch_mode:
                                assert session_count >= 1
                            elif member_state_mode and "--member-state-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif member_state_mode:
                                assert session_count == 2
                            elif department_history_mode and "--department-history-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif department_history_mode:
                                assert session_count == 2
                            elif department_create_mode and "--department-create-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif department_create_mode:
                                assert session_count == 2
                            elif department_patch_mode and "--department-patch-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif department_patch_mode:
                                assert session_count == 2
                            elif department_deactivate_mode and "--department-deactivate-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif department_deactivate_mode:
                                assert session_count == 2
                            else:
                                assert session_count >= (1 if create_mode else 2)
                            active_expected = 51 if member_mode else (2 if expected == 3 or member_create_mode or member_patch_mode else 1)
                            assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE state='ACTIVE'").fetchone()[0] == active_expected
                            if member_create_mode:
                                assert target_user is not None
                                member_created = db.execute("SELECT project_member_id,department_id,project_role,state "
                                    "FROM plm.prj_project_members WHERE project_id=%s AND user_id=%s",
                                    (project, target_user)).fetchone()
                                assert member_created is not None and member_created[1:] == (
                                    department, "IMPLEMENTATION_MEMBER", "ACTIVE")
                                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                    "WHERE target_object_id=%s AND action='PROJECT_MEMBER_CREATED'",
                                    (member_created[0],)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                    "WHERE result_ref_id=%s AND operation='V1_PROJECT_MEMBER_CREATE' "
                                    "AND state='COMPLETED'", (member_created[0],)).fetchone()[0] == 1
                                print("PROJECT_MEMBER_CREATE_DATABASE PASS: one member/Audit/receipt, ACTIVE department", flush=True)
                            if member_patch_mode:
                                assert db.execute("SELECT department_id,project_role,state,lock_version FROM plm.prj_project_members "
                                    "WHERE project_member_id=%s", (patch_member,)).fetchone() == (
                                    patch_department, "CUSTOMER_MEMBER", "ACTIVE", 1)
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_MEMBER_PATCHED'", (patch_member,)).fetchone()[0] == 1
                                print("PROJECT_MEMBER_PATCH_DATABASE PASS: one role/department change, v1, one Audit", flush=True)
                            if member_state_mode:
                                assert db.execute("SELECT state,lock_version,ended_at IS NOT NULL FROM plm.prj_project_members "
                                    "WHERE project_member_id=%s", (state_member,)).fetchone() == ("REMOVED", 3, True)
                                assert db.execute("SELECT action,count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action IN ('PROJECT_MEMBER_SUSPENDED','PROJECT_MEMBER_RESUMED','PROJECT_MEMBER_REMOVED') "
                                    "GROUP BY action ORDER BY action", (state_member,)).fetchall() == [
                                    ("PROJECT_MEMBER_REMOVED", 1), ("PROJECT_MEMBER_RESUMED", 1),
                                    ("PROJECT_MEMBER_SUSPENDED", 1)]
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation IN "
                                    "('V1_PROJECT_MEMBER_SUSPEND','V1_PROJECT_MEMBER_RESUME','V1_PROJECT_MEMBER_REMOVE') "
                                    "AND state='COMPLETED'").fetchone()[0] == 3
                                print("PROJECT_MEMBER_STATE_DATABASE PASS: removed/v3, three Audit, three completed receipts", flush=True)
                            if department_history_mode:
                                assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s",
                                    (project,)).fetchone()[0] == 52
                                assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s "
                                    "AND state='INACTIVE'", (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                    "WHERE action LIKE 'PROJECT_DEPARTMENT_%'").fetchone()[0] == 0
                                print("PROJECT_DEPARTMENT_HISTORY_DATABASE PASS: 52 rows, one inactive, no writes", flush=True)
                            if department_create_mode:
                                created_department = db.execute("SELECT department_id,state,lock_version FROM plm.prj_departments "
                                    "WHERE project_id=%s AND department_code_normalized='new'", (project,)).fetchone()
                                assert created_department is not None and created_department[1:] == ("ACTIVE", 0)
                                assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s",
                                    (project,)).fetchone()[0] == 2
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_DEPARTMENT_CREATED'", (created_department[0],)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                    "WHERE result_ref_id=%s AND operation='V1_PROJECT_DEPARTMENT_CREATE' "
                                    "AND state='COMPLETED'", (created_department[0],)).fetchone()[0] == 1
                                print("PROJECT_DEPARTMENT_CREATE_DATABASE PASS: one new ACTIVE/v0 department, Audit, receipt", flush=True)
                            if department_patch_mode:
                                assert db.execute("SELECT department_code,department_code_normalized,name,state,lock_version "
                                    "FROM plm.prj_departments WHERE department_id=%s", (department,)).fetchone() == (
                                    "NEW", "new", "Synthetic Patched Department", "ACTIVE", 1)
                                assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s",
                                    (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_DEPARTMENT_PATCHED'", (department,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                    "WHERE operation LIKE 'V1_PROJECT_DEPARTMENT_PATCH%%'").fetchone()[0] == 0
                                print("PROJECT_DEPARTMENT_PATCH_DATABASE PASS: target NEW/v1, one Audit, no PATCH receipt", flush=True)
                            if department_deactivate_mode:
                                assert free_department is not None
                                assert db.execute("SELECT state,lock_version FROM plm.prj_departments "
                                    "WHERE department_id=%s", (free_department,)).fetchone() == ("INACTIVE", 1)
                                assert db.execute("SELECT state,lock_version FROM plm.prj_departments "
                                    "WHERE department_id=%s", (department,)).fetchone() == ("ACTIVE", 0)
                                assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s",
                                    (project,)).fetchone()[0] == 2
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_DEPARTMENT_DEACTIVATED'", (free_department,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.prj_department_deactivate_results "
                                    "WHERE department_id=%s", (free_department,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts r "
                                    "JOIN plm.prj_department_deactivate_results d ON d.result_id=r.result_ref_id "
                                    "WHERE r.operation='V1_PROJECT_DEPARTMENT_DEACTIVATE' "
                                    "AND r.state='COMPLETED' AND d.department_id=%s",
                                    (free_department,)).fetchone()[0] == 1
                                print("PROJECT_DEPARTMENT_DEACTIVATE_DATABASE PASS: free INACTIVE/v1, occupied ACTIVE/v0, one Audit/result/receipt", flush=True)
                            if member_mode:
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s", (project,)).fetchone()[0] == 52
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s AND state='REMOVED'", (project,)).fetchone()[0] == 1
                                print("PROJECT_MEMBER_BROWSER_DATABASE PASS: 52 history, 51 active, one removed", flush=True)
                            if expected == 3:
                                if "--create-browser" in sys.argv[1:]:
                                    created = db.execute("SELECT project_id FROM plm.prj_projects WHERE project_code_normalized='create-p04'").fetchone()[0]
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s AND user_id=%s AND project_role='PROJECT_MANAGER'", (created, manager)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_CREATED'", (created,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s AND state='COMPLETED'", (created,)).fetchone()[0] == 1
                            if state_mode:
                                assert db.execute("SELECT state,lock_version FROM plm.auth_users WHERE user_id=%s", (member,)).fetchone() == ("ENABLED", 2)
                                assert db.execute("SELECT count(*) FROM plm.auth_sessions WHERE user_id=%s AND revoked_at IS NOT NULL", (member,)).fetchone()[0] >= 1
                                assert db.execute("SELECT count(*) FROM plm.auth_user_state_results WHERE user_id=%s", (member,)).fetchone()[0] == 2
                                print("USER_STATE_BROWSER_DATABASE PASS: target ENABLED/v2, old member session revoked, two immutable results", flush=True)
                            if name_mode:
                                renamed = "Synthetic Project Renamed Member"
                                assert db.execute("SELECT username_display,username_normalized,state,lock_version FROM plm.auth_users WHERE user_id=%s", (member,)).fetchone() == (renamed, renamed.lower(), "ENABLED", 1)
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='USER_NAME_CHANGED'", (member,)).fetchone()[0] == 1
                                print("USER_NAME_BROWSER_DATABASE PASS: same user renamed/v1, one audit event", flush=True)
                        print(f"PROJECT_BROWSER_DATABASE_COUNTS PASS: {expected} projects, {session_count} sessions, {active_expected} active members", flush=True)
                finally:
                    if proxy:
                        if proxy.poll() is None:
                            try:
                                proxy.stdin.write("STOP\n")
                                proxy.stdin.flush()
                                proxy.wait(timeout=10)
                            except (BrokenPipeError, subprocess.TimeoutExpired):
                                proxy.kill()
                                proxy.wait(timeout=10)
                        proxy.stdin.close()
                        proxy.stdout.close()
                    if server:
                        server.should_exit = True
                    if thread:
                        thread.join(timeout=10)
                        assert not thread.is_alive(), "Owned backend did not stop"
                    if sock:
                        sock.close()
                    source.delete_test_credential(target)
            finally:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
        finally:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        assert admin.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (dbname,)).fetchone()[0] == 0
        assert admin.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (role,)).fetchone()[0] == 0
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = ctypes.c_int
    pointer = ctypes.c_void_p()
    found = library.CredReadW(target, 1, 0, ctypes.byref(pointer))
    if found:
        library.CredFree.argtypes = [ctypes.c_void_p]
        library.CredFree(pointer)
    assert not found and ctypes.get_last_error() == 1168
    print("PROJECT_BROWSER_FIXTURE_CLEANUP PASS: owned services stopped; database/role absent; Vault absence1168", flush=True)


if __name__ == "__main__":
    main()
