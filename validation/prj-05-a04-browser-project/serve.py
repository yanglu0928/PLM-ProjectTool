"""Owned Windows browser/PG fixture for read-only Project UI verification."""

from __future__ import annotations

import ctypes
import hashlib
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
from psycopg.types.json import Jsonb
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
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage


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


def verify_archive_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    route = f"/api/v1/projects/{owned}:archive"
    key = "synthetic-project-archive-0001"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.post(route, headers={"Origin": origin,
            "If-Match": '"v0"', "Idempotency-Key": key}).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.post(route, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"],
            "If-Match": '"v0"', "Idempotency-Key": key})
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=20) as manager:
        login = manager.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["data"]["csrf_token"],
                   "If-Match": '"v0"', "Idempotency-Key": key}
        assert manager.post(route, headers={"Origin": origin,
            "If-Match": '"v0"', "Idempotency-Key": key}).status_code == 403
        denied = manager.post(f"/api/v1/projects/{foreign}:archive", headers=headers)
        assert denied.status_code == 404, denied.text
        missing = manager.post(route, headers={"Origin": origin,
            "X-CSRF-Token": headers["X-CSRF-Token"], "Idempotency-Key": key})
        assert missing.status_code == 428, missing.text
        first = manager.post(route, headers=headers)
        replay = manager.post(route, headers=headers)
        assert first.status_code == replay.status_code == 200, (first.text, replay.text)
        assert first.headers["ETag"] == replay.headers["ETag"] == '"v1"'
        assert first.json()["data"] == replay.json()["data"]
        result = first.json()["data"]
        assert result["project_id"] == str(owned) and result["code"] == "OWNED"
        assert result["name"] == "Synthetic Owned Project" and result["state"] == "ARCHIVED"
        assert result["etag"] == '"v1"'
        conflict = manager.post(route, headers={**headers, "If-Match": '"v1"'})
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "CONFLICT_IDEMPOTENCY", conflict.text
        detail = manager.get(f"/api/v1/projects/{owned}")
        assert detail.status_code == 200 and detail.headers["ETag"] == '"v1"', detail.text
        assert detail.json()["data"]["state"] == "ARCHIVED"
    print("PROJECT_ARCHIVE_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/IfMatch428/200-replay/key-conflict409/detail", flush=True)


def verify_project_patch_http(origin: str, owned: uuid.UUID, foreign: uuid.UUID):
    route = f"/api/v1/projects/{owned}"
    body = {"name": "Synthetic Renamed Project"}
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
        denied = manager.patch(f"/api/v1/projects/{foreign}", headers=headers, json=body)
        assert denied.status_code == 404, denied.text
        missing = manager.patch(route, headers={"Origin": origin,
            "X-CSRF-Token": headers["X-CSRF-Token"]}, json=body)
        assert missing.status_code == 428, missing.text
        malformed = manager.patch(route, headers=headers, json={"code": "OTHER"})
        assert malformed.status_code == 400, malformed.text
        first = manager.patch(route, headers=headers, json=body)
        assert first.status_code == 200 and first.headers["ETag"] == '"v1"', first.text
        assert first.json()["data"]["project_id"] == str(owned)
        assert first.json()["data"]["code"] == "OWNED"
        assert first.json()["data"]["name"] == body["name"]
        assert first.json()["data"]["state"] == "ACTIVE"
        assert first.json()["data"]["etag"] == '"v1"'
        stale = manager.patch(route, headers=headers, json=body)
        assert stale.status_code == 409 and stale.json()["error"]["code"] == "CONFLICT_VERSION", stale.text
        same = manager.patch(route, headers={**headers, "If-Match": '"v1"'}, json=body)
        assert same.status_code == 200 and same.headers["ETag"] == '"v2"', same.text
        assert same.json()["data"]["name"] == body["name"]
        detail = manager.get(route)
        assert detail.status_code == 200 and detail.headers["ETag"] == '"v2"', detail.text
        assert detail.json()["data"]["name"] == body["name"]
    print("PROJECT_PATCH_HTTP PASS: anonymous401/admin404/CSRF403/foreign404/IfMatch428/body400/v1/stale409/same-v2/detail", flush=True)


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


def verify_document_history_http(origin: str, project: uuid.UUID, foreign: uuid.UUID):
    route = f"/api/v1/projects/{project}/documents"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.get(route).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200
        denied = admin.get(route)
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND", denied.text
    with httpx.Client(base_url=origin, timeout=20) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        first = member.get(route, params={"page_size": 50})
        assert first.status_code == 200, first.text
        page = first.json()["data"]
        assert len(page["items"]) == 50 and page["has_more"] and page["next_cursor"]
        assert all(item["scope"] == "PROJECT" and item["category"] == "PROJECT_RECORD" for item in page["items"])
        assert all("storage_locator" not in item and "content" not in item for item in page["items"])
        second = member.get(route, params={"page_size": 50, "cursor": page["next_cursor"]})
        assert second.status_code == 200, second.text
        end = second.json()["data"]
        assert len(end["items"]) == 1 and not end["has_more"] and end["next_cursor"] is None
        ids = [item["document_id"] for item in page["items"] + end["items"]]
        assert len(set(ids)) == 51
        assert {item["title"] for item in page["items"] + end["items"]} == {
            f"Synthetic Browser Document {index:02d}" for index in range(51)}
        denied = member.get(f"/api/v1/projects/{foreign}/documents")
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND", denied.text
        cross = member.get(f"/api/v1/projects/{foreign}/documents/{ids[0]}")
        assert cross.status_code == 404
        detail = member.get(f"{route}/{ids[0]}")
        assert detail.status_code == 200 and detail.headers["ETag"] == detail.json()["data"]["etag"]
        assert detail.json()["data"]["document_id"] == ids[0]
        with httpx.Client(base_url=origin, timeout=20) as other_session:
            login = other_session.post("/api/v1/auth/login", headers={"Origin": origin},
                json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
            assert login.status_code == 200
            bad_cursor = other_session.get(route, params={"page_size": 50, "cursor": page["next_cursor"]})
            assert bad_cursor.status_code == 400, bad_cursor.text
    print("DOCUMENT_HISTORY_HTTP PASS: anonymous401/admin404/foreign404, 50+1 signed cursor, detail ETag, session-bound cursor", flush=True)


def verify_document_version_http(origin: str, project: uuid.UUID, foreign: uuid.UUID):
    with httpx.Client(base_url=origin, timeout=20) as member:
        assert member.get(f"/api/v1/projects/{project}/documents").status_code == 401
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        listing = member.get(f"/api/v1/projects/{project}/documents", params={"page_size": 50})
        assert listing.status_code == 200, listing.text
        document_id = listing.json()["data"]["items"][0]["document_id"]
        route = f"/api/v1/projects/{project}/documents/{document_id}/versions"
        result = member.get(route, params={"page_size": 50})
        assert result.status_code == 200, result.text
        page = result.json()["data"]
        assert len(page["items"]) == 1 and page["next_cursor"] is None and not page["has_more"]
        item = page["items"][0]
        assert item["version_no"] == 1 and item["availability_state"] == "AVAILABLE"
        assert item["content_sha256"] == "a" * 64 and item["size_bytes"] == 7
        assert "storage_locator" not in item and "content" not in item
        detail = member.get(f"{route}/{item['document_version_id']}")
        assert detail.status_code == 200 and detail.json()["data"] == item
        denied = member.get(f"/api/v1/projects/{foreign}/documents/{document_id}/versions")
        assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    print("DOCUMENT_VERSION_HTTP PASS: anonymous401/foreign404, AVAILABLE metadata list/detail, no locator", flush=True)


def verify_document_download_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                                  document_id: uuid.UUID, version_id: uuid.UUID,
                                  content: bytes):
    route = f"/api/v1/projects/{project}/documents/{document_id}/versions/{version_id}/content"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.get(route).status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        response = member.get(route)
        assert response.status_code == 200, response.text
        assert response.content == content and hashlib.sha256(response.content).digest() == hashlib.sha256(content).digest()
        assert response.headers["content-length"] == str(len(content))
        assert response.headers["content-type"].startswith("text/plain")
        assert response.headers["content-disposition"] == f'attachment; filename="document-{version_id}.bin"'
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        cross = member.get(f"/api/v1/projects/{foreign}/documents/{document_id}/versions/{version_id}/content")
        assert cross.status_code == 404 and cross.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        ranged = member.get(route, headers={"Range": "bytes=0-1"})
        assert ranged.status_code == 400 and ranged.json()["error"]["code"] == "REQUEST_MALFORMED"
    print("DOCUMENT_DOWNLOAD_HTTP PASS: real bytes/hash, attachment/no-store/nosniff, anonymous401/foreign404/range400", flush=True)


def verify_document_upload_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                                dbname: str, data_root: Path):
    """Real loopback HTTP plus isolated PG/file proof; browser UI is a separate test."""
    base = f"/api/v1/projects/{project}/document-uploads"
    content_one = b"%PDF-1.7\nPLM synthetic network upload v1\n%%EOF\n"
    content_two = b"%PDF-1.7\nPLM synthetic network upload v2\n%%EOF\n"
    body = {"purpose": "SOURCE", "category": "PROJECT_RECORD", "title": "Synthetic Network Upload",
            "display_name": "synthetic-upload.pdf", "size_hint_bytes": len(content_one),
            "mime_hint": "application/pdf"}

    def create(client, csrf, key, payload):
        result = client.post(base, headers={"Origin": origin, "X-CSRF-Token": csrf,
            "Idempotency-Key": key}, json=payload)
        assert result.status_code == 201, result.text
        assert result.headers["Cache-Control"] == "no-store"
        created = result.json()["data"]
        assert result.headers["Location"] == base + "/" + created["upload_id"]
        assert len(created["upload_token"]) == 43
        return created

    def stage(client, csrf, created, content):
        route = base + "/" + created["upload_id"] + "/content"
        request = client.build_request("PUT", route, headers={"Origin": origin,
            "X-CSRF-Token": csrf, "X-Upload-Token": created["upload_token"],
            "X-Content-SHA256": hashlib.sha256(content).hexdigest(),
            "Content-Type": "application/octet-stream"}, content=content)
        assert request.headers["Content-Length"] == str(len(content))
        result = client.send(request)
        assert result.status_code == 200, result.text
        assert result.headers["Cache-Control"] == "no-store"
        data = result.json()["data"]
        assert data["upload_id"] == created["upload_id"]
        assert data["size_bytes"] == len(content)
        assert data["sha256"] == hashlib.sha256(content).hexdigest()
        assert data["detected_mime"] == "application/pdf"
        return data

    with httpx.Client(base_url=origin, timeout=30) as anonymous:
        denied = anonymous.post(base, headers={"Origin": origin,
            "X-CSRF-Token": "a" * 64, "Idempotency-Key": "synthetic-upload-anon-01"}, json=body)
        assert denied.status_code == 401, denied.text
    with httpx.Client(base_url=origin, timeout=30) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        denied = admin.post(base, headers={"Origin": origin,
            "X-CSRF-Token": login.json()["data"]["csrf_token"],
            "Idempotency-Key": "synthetic-upload-admin-01"}, json=body)
        assert denied.status_code == 404, denied.text
    with httpx.Client(base_url=origin, timeout=30) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        csrf = login.json()["data"]["csrf_token"]
        no_csrf = member.post(base, headers={"Origin": origin,
            "Idempotency-Key": "synthetic-upload-nocsrf-01"}, json=body)
        assert no_csrf.status_code == 403, no_csrf.text
        foreign_create = member.post(f"/api/v1/projects/{foreign}/document-uploads",
            headers={"Origin": origin, "X-CSRF-Token": csrf,
                "Idempotency-Key": "synthetic-upload-foreign-01"}, json=body)
        assert foreign_create.status_code == 404, foreign_create.text

        first = create(member, csrf, "synthetic-upload-create-v1", body)
        first_data = stage(member, csrf, first, content_one)
        route = base + "/" + first["upload_id"] + ":commit"
        headers = {"Origin": origin, "X-CSRF-Token": csrf,
                   "Idempotency-Key": "synthetic-upload-commit-v1"}
        committed = member.post(route, headers=headers)
        replay = member.post(route, headers=headers)
        assert committed.status_code == replay.status_code == 201, (committed.text, replay.text)
        assert committed.json()["data"] == replay.json()["data"]
        result = committed.json()["data"]
        assert result["upload_id"] == first["upload_id"] and result["version_no"] == 1
        document_id = result["document_id"]
        detail_path = f"/api/v1/projects/{project}/documents/{document_id}"
        detail = member.get(detail_path)
        assert detail.status_code == 200, detail.text
        parent_etag = detail.headers["ETag"]
        assert parent_etag == '"v1"'
        downloaded = member.get(detail_path + f"/versions/{result['document_version_id']}/content")
        assert downloaded.status_code == 200 and downloaded.content == content_one, downloaded.text

        second_body = {"purpose": "SOURCE", "display_name": "synthetic-upload-v2.pdf",
                       "size_hint_bytes": len(content_two), "mime_hint": "application/pdf",
                       "document_id": document_id,
                       "supersedes_version_id": result["document_version_id"]}
        second = create(member, csrf, "synthetic-upload-create-v2", second_body)
        second_data = stage(member, csrf, second, content_two)
        second_commit = member.post(base + "/" + second["upload_id"] + ":commit",
            headers={"Origin": origin, "X-CSRF-Token": csrf,
                "Idempotency-Key": "synthetic-upload-commit-v2", "If-Match": parent_etag})
        assert second_commit.status_code == 201, second_commit.text
        second_result = second_commit.json()["data"]
        assert second_result["document_id"] == document_id and second_result["version_no"] == 2
        assert second_result["document_version_id"] != result["document_version_id"]
        downloaded_two = member.get(detail_path + f"/versions/{second_result['document_version_id']}/content")
        assert downloaded_two.status_code == 200 and downloaded_two.content == content_two, downloaded_two.text
        stale = member.post(base + "/" + second["upload_id"] + ":commit",
            headers={"Origin": origin, "X-CSRF-Token": csrf,
                "Idempotency-Key": "synthetic-upload-commit-new-key", "If-Match": parent_etag})
        assert stale.status_code == 409, stale.text

        stopped = create(member, csrf, "synthetic-upload-create-abort", body)
        stage(member, csrf, stopped, content_one)
        abort_path = base + "/" + stopped["upload_id"] + ":abort"
        abort_headers = {"Origin": origin, "X-CSRF-Token": csrf,
                         "Idempotency-Key": "synthetic-upload-abort-key"}
        aborted = member.post(abort_path, headers=abort_headers)
        abort_replay = member.post(abort_path, headers=abort_headers)
        assert aborted.status_code == abort_replay.status_code == 200
        assert aborted.json()["data"] == abort_replay.json()["data"]
        assert aborted.json()["data"]["cleanup_pending"] is True

    with source.connect(dbname) as db:
        rows = db.execute("SELECT d.document_id,v.document_version_id,v.version_no,f.storage_locator,"
            "f.sha256,f.size_bytes,f.file_state FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "JOIN plm.doc_file_objects f ON f.file_object_id=v.file_object_id "
            "WHERE d.document_id=%s ORDER BY v.version_no", (uuid.UUID(document_id),)).fetchall()
        assert len(rows) == 2 and [item[2] for item in rows] == [1, 2]
        for row, content, staged in zip(rows, (content_one, content_two), (first_data, second_data)):
            assert row[0] == uuid.UUID(document_id) and row[6] == "AVAILABLE"
            assert row[4] == hashlib.sha256(content).digest() and row[5] == len(content)
            locator = row[3]
            assert locator.startswith(f"projects/{project.hex}/objects/")
            physical = data_root / locator
            assert physical.is_file() and physical.read_bytes() == content
            assert staged["sha256"] == hashlib.sha256(content).hexdigest()
        assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE job_type='DOCUMENT_PARSE' "
            "AND job_id IN (%s,%s)", (uuid.UUID(result["parse_job_id"]),
                                     uuid.UUID(second_result["parse_job_id"]))).fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_COMMIT'").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_ABORT'").fetchone()[0] == 1
        assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s",
            (uuid.UUID(stopped["upload_id"]),)).fetchone() == ("ABORTED",)
        assert db.execute("SELECT count(*) FROM plm.doc_document_versions WHERE project_id=%s",
            (foreign,)).fetchone()[0] == 0
    print("DOCUMENT_UPLOAD_NETWORK PASS: real HTTP length/hash, v1/v2/abort, downloads, PG files/jobs/audit, isolation", flush=True)


def verify_document_parse_http(origin: str, project: uuid.UUID, foreign: uuid.UUID,
                               document_id: uuid.UUID, version_id: uuid.UUID,
                               expected_ids: tuple[uuid.UUID, ...]):
    route = f"/api/v1/projects/{project}/documents/{document_id}/versions/{version_id}/parses"
    with httpx.Client(base_url=origin, timeout=20) as anonymous:
        assert anonymous.get(route + "?page_size=2").status_code == 401
    with httpx.Client(base_url=origin, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Admin", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        assert admin.get(route + "?page_size=2").status_code == 404
    with httpx.Client(base_url=origin, timeout=20) as member:
        login = member.post("/api/v1/auth/login", headers={"Origin": origin},
            json={"username": "Synthetic Project Member", "password": "synthetic-project-only-password"})
        assert login.status_code == 200, login.text
        first = member.get(route + "?page_size=2")
        assert first.status_code == 200 and first.headers["Cache-Control"] == "no-store", first.text
        data = first.json()["data"]
        assert len(data["items"]) == 2 and data["has_more"] and data["next_cursor"]
        second = member.get(route, params={"page_size": 2, "cursor": data["next_cursor"]})
        assert second.status_code == 200, second.text
        tail = second.json()["data"]
        assert len(tail["items"]) == 1 and not tail["has_more"] and tail["next_cursor"] is None
        items = data["items"] + tail["items"]
        assert {uuid.UUID(item["parse_record_id"]) for item in items} == set(expected_ids)
        assert all(item["parse_state"] == "PENDING" and item["result_ref"] is None for item in items)
        assert all("storage_locator" not in item and "result_sha256" not in item for item in items)
        foreign_route = f"/api/v1/projects/{foreign}/documents/{document_id}/versions/{version_id}/parses"
        assert member.get(foreign_route).status_code == 404
    print("DOCUMENT_PARSE_NETWORK PASS: real Session, 2+1 cursor, pending-only safe projection, isolation", flush=True)


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
                    archive_mode = "--archive-api-only" in sys.argv[1:] or "--archive-browser" in sys.argv[1:]
                    project_patch_mode = ("--project-patch-api-only" in sys.argv[1:]
                                          or "--project-patch-browser" in sys.argv[1:])
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
                    document_history_mode = ("--document-history-api-only" in sys.argv[1:]
                                             or "--document-history-browser" in sys.argv[1:]
                                             or "--document-detail-browser" in sys.argv[1:]
                                             or "--document-version-api-only" in sys.argv[1:]
                                             or "--document-version-browser" in sys.argv[1:]
                                             or "--document-download-api-only" in sys.argv[1:]
                                             or "--document-download-browser" in sys.argv[1:]
                                             or "--document-parse-api-only" in sys.argv[1:]
                                             or "--document-parse-browser" in sys.argv[1:])
                    document_version_mode = ("--document-version-api-only" in sys.argv[1:]
                                             or "--document-version-browser" in sys.argv[1:])
                    document_download_mode = ("--document-download-api-only" in sys.argv[1:]
                                              or "--document-download-browser" in sys.argv[1:]
                                              or "--document-parse-api-only" in sys.argv[1:]
                                              or "--document-parse-browser" in sys.argv[1:])
                    document_parse_mode = ("--document-parse-api-only" in sys.argv[1:]
                                           or "--document-parse-browser" in sys.argv[1:])
                    document_upload_mode = ("--document-upload-api-only" in sys.argv[1:]
                                            or "--document-upload-browser" in sys.argv[1:])
                    download_document_id = download_version_id = None
                    parse_record_ids: tuple[uuid.UUID, ...] = ()
                    member_mode = ("--member-browser" in sys.argv[1:]
                                   or "--member-api-only" in sys.argv[1:])
                    if sum((create_mode, archive_mode, project_patch_mode, state_mode, name_mode, member_mode, member_create_mode,
                            member_patch_mode, member_state_mode, department_history_mode,
                            department_create_mode, department_patch_mode,
                            department_deactivate_mode, document_history_mode,
                            document_upload_mode)) > 1:
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
                    if document_history_mode:
                        for index in range(51):
                            document_id = db.execute("INSERT INTO plm.doc_documents "
                                "(scope,project_id,document_category,title,original_display_name,created_by) "
                                "VALUES ('PROJECT',%s,'PROJECT_RECORD',%s,%s,%s) RETURNING document_id",
                                (project, f"Synthetic Browser Document {index:02d}",
                                 ("synthetic-00.txt" if document_download_mode and index == 0
                                  else f"synthetic-{index:02d}.pdf"), member)).fetchone()[0]
                            if document_download_mode and index == 0:
                                download_document_id = document_id
                            if document_version_mode:
                                file_id = db.execute("INSERT INTO plm.doc_file_objects "
                                    "(scope,project_id,storage_class,storage_locator,original_name_metadata,"
                                    "created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
                                    "VALUES ('PROJECT',%s,'PERSISTENT',%s,%s,%s,'AVAILABLE',%s,7,"
                                    "'application/pdf',clock_timestamp()+interval '1 minute') RETURNING file_object_id",
                                    (project, f"synthetic/{uuid.uuid4().hex}", f"synthetic-{index:02d}.pdf",
                                     member, bytes.fromhex("a" * 64))).fetchone()[0]
                                version_id = db.execute("INSERT INTO plm.doc_document_versions "
                                    "(document_id,scope,project_id,version_no,file_object_id,content_sha256,"
                                    "size_bytes,detected_mime,created_by) "
                                    "VALUES (%s,'PROJECT',%s,1,%s,%s,7,'application/pdf',%s) "
                                    "RETURNING document_version_id",
                                    (document_id, project, file_id, bytes.fromhex("a" * 64), member)).fetchone()[0]
                                db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                                    "effective_version_ref=%s,lock_version=1 WHERE document_id=%s",
                                    (version_id, version_id, document_id))
                        db.execute("INSERT INTO plm.doc_documents "
                            "(scope,project_id,document_category,title,original_display_name,created_by,document_state) "
                            "VALUES ('PROJECT',%s,'PROJECT_RECORD','Synthetic Restricted Document','restricted.pdf',%s,'RESTRICTED')",
                            (project, member))
                        db.execute("INSERT INTO plm.doc_documents "
                            "(scope,project_id,document_category,title,original_display_name,created_by) "
                            "VALUES ('PROJECT',%s,'PROJECT_RECORD','Synthetic Foreign Document','foreign.pdf',%s)",
                            (foreign, admin_user))
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
                        download_content = b"PLM Project Tool isolated document download proof\n"
                        if document_download_mode:
                            assert download_document_id is not None
                            storage = LocalFileStorage(settings.data_root)
                            file_id = uuid.uuid4()
                            stage, final = storage.locators(scope="PROJECT", project_id=project,
                                                            file_object_id=file_id)
                            digest = hashlib.sha256(download_content).digest()
                            with storage.reserve_staging(stage) as stream:
                                stream.write(download_content)
                            storage.publish_verified(stage, final, expected_sha256=digest,
                                                     expected_size=len(download_content), max_bytes=100_000_000)
                            with source.connect(dbname) as db:
                                db.execute("INSERT INTO plm.doc_file_objects "
                                    "(file_object_id,scope,project_id,storage_class,storage_locator,"
                                    "original_name_metadata,created_by,file_state,sha256,size_bytes,"
                                    "detected_mime,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,"
                                    "'synthetic-00.txt',%s,'AVAILABLE',%s,%s,'text/plain',"
                                    "clock_timestamp()+interval '1 minute')",
                                    (file_id, project, final, member, digest, len(download_content)))
                                download_version_id = db.execute("INSERT INTO plm.doc_document_versions "
                                    "(document_id,scope,project_id,version_no,file_object_id,content_sha256,"
                                    "size_bytes,detected_mime,created_by) VALUES "
                                    "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s) "
                                    "RETURNING document_version_id",
                                    (download_document_id, project, file_id, digest, len(download_content), member)).fetchone()[0]
                                db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                                    "effective_version_ref=%s,lock_version=1 WHERE document_id=%s",
                                    (download_version_id, download_version_id, download_document_id))
                                if document_parse_mode:
                                    job = db.execute("INSERT INTO plm.job_jobs "
                                        "(owner_module,job_type,scope,project_id,actor_ref,trace_id,"
                                        "payload_refs,idempotency_key,max_attempts) VALUES "
                                        "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,"
                                        "'synthetic-parse-read',3) RETURNING job_id",
                                        (project, member, str(uuid.uuid4()), Jsonb({
                                            "document_id": str(download_document_id),
                                            "document_version_id": str(download_version_id),
                                        }))).fetchone()[0]
                                    records = []
                                    for attempt in (1, 2, 3):
                                        records.append(db.execute("INSERT INTO plm.doc_parse_records "
                                            "(document_version_id,scope,project_id,parser_profile,"
                                            "parser_version,job_ref,attempt_no) VALUES "
                                            "(%s,'PROJECT',%s,'SYNTHETIC_METADATA','1',%s,%s) "
                                            "RETURNING parse_record_id",
                                            (download_version_id, project, job, attempt)).fetchone()[0])
                                    parse_record_ids = tuple(records)
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
                        if state_mode or name_mode or document_upload_mode:
                            stack.enter_context(patch(
                                "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                                return_value=object()))
                            stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                                return_value=HmacUploadTokenIssuer(
                                    provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                                    key_ref="synthetic-browser-upload-token")))
                        with redirect_stdout(logs):
                            factory = (production.create_production_platform_write_app if state_mode or name_mode or document_upload_mode
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
                        elif "--archive-api-only" in sys.argv[1:]:
                            verify_archive_http(origin, project, foreign)
                        elif "--project-patch-api-only" in sys.argv[1:]:
                            verify_project_patch_http(origin, project, foreign)
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
                        elif "--document-history-api-only" in sys.argv[1:]:
                            verify_document_history_http(origin, project, foreign)
                        elif "--document-version-api-only" in sys.argv[1:]:
                            verify_document_version_http(origin, project, foreign)
                        elif "--document-download-api-only" in sys.argv[1:]:
                            assert download_document_id is not None and download_version_id is not None
                            verify_document_download_http(origin, project, foreign,
                                download_document_id, download_version_id, download_content)
                        elif "--document-parse-api-only" in sys.argv[1:]:
                            assert download_document_id is not None and download_version_id is not None
                            verify_document_parse_http(origin, project, foreign,
                                download_document_id, download_version_id, parse_record_ids)
                        elif "--document-upload-api-only" in sys.argv[1:]:
                            verify_document_upload_http(origin, project, foreign, dbname, settings.data_root)
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
                            elif archive_mode and "--archive-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif archive_mode:
                                assert session_count == 2
                            elif project_patch_mode and "--project-patch-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif project_patch_mode:
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
                            elif document_history_mode and ("--document-history-browser" in sys.argv[1:]
                                                            or "--document-detail-browser" in sys.argv[1:]
                                                            or "--document-version-browser" in sys.argv[1:]
                                                            or "--document-download-browser" in sys.argv[1:]
                                                            or "--document-parse-browser" in sys.argv[1:]):
                                assert session_count >= 1
                            elif "--document-parse-api-only" in sys.argv[1:]:
                                assert session_count == 2
                            elif document_version_mode or document_download_mode:
                                assert session_count == 1
                            elif "--document-upload-browser" in sys.argv[1:]:
                                assert session_count >= 1
                            elif document_upload_mode:
                                assert session_count == 2
                            elif document_history_mode:
                                assert session_count == 3
                            else:
                                assert session_count >= (1 if create_mode else 2)
                            active_expected = 51 if member_mode else (2 if expected == 3 or member_create_mode or member_patch_mode else 1)
                            assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE state='ACTIVE'").fetchone()[0] == active_expected
                            if archive_mode:
                                assert db.execute("SELECT state,lock_version FROM plm.prj_projects WHERE project_id=%s",
                                    (project,)).fetchone() == ("ARCHIVED", 1)
                                assert db.execute("SELECT state,lock_version FROM plm.prj_projects WHERE project_id=%s",
                                    (foreign,)).fetchone() == ("ACTIVE", 0)
                                assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s "
                                    "AND project_role='PROJECT_MANAGER' AND state='ACTIVE'",
                                    (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_ARCHIVED'", (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                    "WHERE operation='V1_PROJECT_ARCHIVE' AND state='COMPLETED' "
                                    "AND result_ref_id=%s", (project,)).fetchone()[0] == 1
                                print("PROJECT_ARCHIVE_DATABASE PASS: owned ARCHIVED/v1, foreign ACTIVE/v0, manager retained, one Audit/receipt", flush=True)
                            if project_patch_mode:
                                expected_name = ("Synthetic Browser Renamed Project" if "--project-patch-browser" in sys.argv[1:]
                                                 else "Synthetic Renamed Project")
                                expected_version = 1 if "--project-patch-browser" in sys.argv[1:] else 2
                                assert db.execute("SELECT project_code,name,state,lock_version FROM plm.prj_projects "
                                    "WHERE project_id=%s", (project,)).fetchone() == (
                                    "OWNED", expected_name, "ACTIVE", expected_version)
                                assert db.execute("SELECT name,state,lock_version FROM plm.prj_projects "
                                    "WHERE project_id=%s", (foreign,)).fetchone() == (
                                    "Synthetic Foreign Project", "ACTIVE", 0)
                                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                    "AND action='PROJECT_PATCHED'", (project,)).fetchone()[0] == expected_version
                                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                    "WHERE operation LIKE 'V1_PROJECT_PATCH%%'").fetchone()[0] == 0
                                print(f"PROJECT_PATCH_DATABASE PASS: owned ACTIVE/v{expected_version}, foreign unchanged, "
                                      f"{expected_version} Audit, no PATCH receipt", flush=True)
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
                            if document_history_mode:
                                assert db.execute("SELECT count(*) FROM plm.doc_documents WHERE project_id=%s "
                                    "AND document_state='ACTIVE'", (project,)).fetchone()[0] == 51
                                assert db.execute("SELECT count(*) FROM plm.doc_documents WHERE project_id=%s "
                                    "AND document_state='RESTRICTED'", (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.doc_documents WHERE project_id=%s",
                                    (foreign,)).fetchone()[0] == 1
                                print("DOCUMENT_HISTORY_DATABASE PASS: owned 51 ACTIVE + 1 RESTRICTED, foreign 1", flush=True)
                            if document_version_mode:
                                assert db.execute("SELECT count(*) FROM plm.doc_document_versions v "
                                    "JOIN plm.doc_file_objects f ON f.file_object_id=v.file_object_id "
                                    "WHERE v.project_id=%s AND v.availability_state='AVAILABLE' "
                                    "AND f.file_state='AVAILABLE' AND f.sha256=v.content_sha256 "
                                    "AND f.size_bytes=v.size_bytes AND f.detected_mime=v.detected_mime",
                                    (project,)).fetchone()[0] == 51
                                assert db.execute("SELECT count(*) FROM plm.doc_document_versions "
                                    "WHERE project_id=%s", (foreign,)).fetchone()[0] == 0
                                print("DOCUMENT_VERSION_DATABASE PASS: 51 matching AVAILABLE metadata, foreign 0", flush=True)
                            if document_download_mode:
                                assert db.execute("SELECT count(*) FROM plm.doc_document_versions "
                                    "WHERE project_id=%s AND availability_state='AVAILABLE'",
                                    (project,)).fetchone()[0] == 1
                                assert db.execute("SELECT count(*) FROM plm.doc_document_versions "
                                    "WHERE project_id=%s", (foreign,)).fetchone()[0] == 0
                                print("DOCUMENT_DOWNLOAD_DATABASE PASS: one real-file-backed AVAILABLE version, foreign 0", flush=True)
                            if document_parse_mode:
                                assert download_version_id is not None
                                rows = db.execute("SELECT parse_record_id,parse_state,job_ref,result_ref "
                                    "FROM plm.doc_parse_records WHERE document_version_id=%s",
                                    (download_version_id,)).fetchall()
                                assert len(rows) == 3 and {row[0] for row in rows} == set(parse_record_ids)
                                assert all(row[1] == "PENDING" and row[3] is None for row in rows)
                                assert len({row[2] for row in rows}) == 1
                                assert db.execute("SELECT count(*) FROM plm.doc_parse_records "
                                    "WHERE project_id=%s", (foreign,)).fetchone()[0] == 0
                                print("DOCUMENT_PARSE_DATABASE PASS: three synthetic PENDING attempts, real file-backed version, foreign zero", flush=True)
                            if "--document-upload-browser" in sys.argv[1:]:
                                versions = db.execute("SELECT v.document_id,v.version_no,f.storage_locator,f.sha256,f.size_bytes "
                                    "FROM plm.doc_document_versions v JOIN plm.doc_file_objects f "
                                    "ON f.file_object_id=v.file_object_id WHERE v.project_id=%s "
                                    "AND v.availability_state='AVAILABLE' AND f.file_state='AVAILABLE' "
                                    "ORDER BY v.version_no", (project,)).fetchall()
                                assert len(versions) == 2 and [v[1] for v in versions] == [1, 2]
                                assert versions[0][0] == versions[1][0]
                                for version, expected_name in zip(versions, ("synthetic-upload-v1.pdf", "synthetic-upload-v2.pdf")):
                                    _, _, locator, digest, size = version
                                    content = (settings.data_root / locator).read_bytes()
                                    expected_content = (Path(__file__).parent / expected_name).read_bytes()
                                    assert content == expected_content
                                    assert len(content) == size and hashlib.sha256(content).digest() == digest
                                assert db.execute("SELECT count(*) FROM plm.job_jobs "
                                    "WHERE job_type='DOCUMENT_PARSE' AND project_id=%s", (project,)).fetchone()[0] == 2
                                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                    "WHERE action='DOCUMENT_UPLOAD_COMMIT'").fetchone()[0] == 2
                                assert db.execute("SELECT count(*) FROM plm.doc_document_versions "
                                    "WHERE project_id=%s", (foreign,)).fetchone()[0] == 0
                                print("DOCUMENT_UPLOAD_BROWSER_DATABASE PASS: two disk-backed versions, two parse jobs/audits, foreign zero", flush=True)
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
    assert not Path(directory).exists(), "Temporary file root was not cleaned"
    print("PROJECT_BROWSER_FIXTURE_CLEANUP PASS: owned services stopped; database/role absent; Vault absence1168", flush=True)


if __name__ == "__main__":
    main()
