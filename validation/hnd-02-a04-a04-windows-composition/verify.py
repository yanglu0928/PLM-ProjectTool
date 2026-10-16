"""Windows 11 real PostgreSQL/HTTP proof for Handover Action reads."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_handover_action_read import (
    HANDOVER_ACTION_CURSOR_KEY_REF,
    create_windows_handover_action_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "hnd_action_http_fixture",
)
connect, seed_user, Guard = fixture.connect, fixture.seed_user, fixture.Guard
TOKEN = b"h" * 32


class Keys:
    def resolve_key(self, key_ref: str) -> bytes | None:
        return b"c" * 32 if key_ref == HANDOVER_ACTION_CURSOR_KEY_REF else None


class Sessions:
    def validate(self, token: bytes):
        if token != TOKEN:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def expect(response, status: int) -> dict:
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()


def main() -> None:
    name = "hnd02a04a04_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                fixed = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
                with connect(name) as db:
                    user_id = seed_user(db, "HTTP Action Reader", "NONE", TOKEN)
                    project_id = db.execute(
                        "INSERT INTO plm.prj_projects"
                        "(project_code,project_code_normalized,name,created_by) "
                        "VALUES ('HNDHTTP','hndhttp','HTTP Handover',%s) "
                        "RETURNING project_id",
                        (user_id,),
                    ).fetchone()[0]
                    department_id = db.execute(
                        "INSERT INTO plm.prj_departments"
                        "(project_id,department_code,department_code_normalized,name) "
                        "VALUES (%s,'HND','hnd','Handover') RETURNING department_id",
                        (project_id,),
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO plm.prj_project_members"
                        "(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                        (project_id, user_id, department_id),
                    )

                    def seed_action(title: str) -> uuid.UUID:
                        action_id = uuid.uuid4()
                        with db.transaction():
                            db.execute(
                                "INSERT INTO plm.hnd_action_items"
                                "(action_item_id,project_id,source_kind,human_source_reason,"
                                "action_type,title,requested_input_spec,owner_ref,due_at,"
                                "priority,action_state,created_by,created_reason,created_at,"
                                "updated_at,lock_version) VALUES "
                                "(%s,%s,'HUMAN','Meeting','PROVIDE_INFO',%s,"
                                "'{\"fields\":[{\"name\":\"answer\"}]}'::jsonb,%s,"
                                "%s + interval '7 days','HIGH','OPEN',%s,'HTTP fixture',"
                                "%s,%s,0)",
                                (action_id, project_id, title, user_id, fixed,
                                 user_id, fixed, fixed),
                            )
                            db.execute(
                                "INSERT INTO plm.hnd_action_state_events"
                                "(action_state_event_id,action_item_id,project_id,sequence_no,"
                                "from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                                "VALUES (%s,%s,%s,0,NULL,'OPEN',%s,'HTTP fixture',%s,%s)",
                                (uuid.uuid4(), action_id, project_id, user_id,
                                 fixed, uuid.uuid4()),
                            )
                        return action_id

                    first, second = seed_action("First"), seed_action("Second")
                    before = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.hnd_action_state_events)"
                    ).fetchone()

                router = create_windows_handover_action_read_router(
                    runtime, sessions=Sessions(),
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                    license_guard=Guard(), resolver=Keys(),
                )
                app = create_app(handover_action_read_router=router)
                path = f"/api/v1/projects/{project_id}/handover-action-items"
                headers = {"cookie": "plm_session=" + TOKEN.hex()}
                with TestClient(
                    app, base_url="https://plm.example.test",
                ) as client:
                    page_one = expect(client.get(
                        path + "?page_size=1", headers=headers,
                    ), 200)["data"]
                    assert len(page_one["items"]) == 1 and page_one["has_more"]
                    page_two = expect(client.get(
                        path + "?page_size=1&cursor=" + page_one["next_cursor"],
                        headers=headers,
                    ), 200)["data"]
                    assert len(page_two["items"]) == 1 and not page_two["has_more"]
                    assert {
                        item["action_item_id"]
                        for item in page_one["items"] + page_two["items"]
                    } == {str(first), str(second)}
                    detail_response = client.get(
                        path + "/" + str(first), headers=headers,
                    )
                    detail = expect(detail_response, 200)["data"]
                    assert detail_response.headers["etag"] == '"v0"'
                    assert detail["current_event"]["to_state"] == "OPEN"
                    assert "trace_id" not in detail["current_event"]
                    bad_cursor = page_one["next_cursor"][:-1] + "!"
                    expect(client.get(
                        path + "?page_size=1&cursor=" + bad_cursor,
                        headers=headers,
                    ), 400)
                    expect(client.get(
                        path + "/" + str(uuid.uuid4()), headers=headers,
                    ), 404)
                    expect(client.get(path), 401)

                with connect(name) as db:
                    after = db.execute(
                        "SELECT (SELECT count(*) FROM plm.aud_events),"
                        "(SELECT count(*) FROM plm.plt_idempotency_receipts),"
                        "(SELECT count(*) FROM plm.hnd_action_state_events)"
                    ).fetchone()
                    assert before == after, (before, after)
                command.check(cfg)
                print(
                    "HND_02_A04_A04_WINDOWS_COMPOSITION_PASS: Windows read "
                    "composition, dedicated synthetic key, real PostgreSQL 18 "
                    "and HTTP list/cursor/detail/denial with zero business writes"
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
