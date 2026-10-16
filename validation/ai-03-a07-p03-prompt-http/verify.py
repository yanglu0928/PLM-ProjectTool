"""Disposable ASGI/PG18 proof of optional Prompt metadata LIST/GET."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.prompt_metadata import create_ai_prompt_read_router
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.prompt_metadata import PromptMetadataService
from plm_assistant.modules.ai.infrastructure.prompt_metadata_repository import SqlAlchemyPromptMetadataRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a03-model-metadata" / "verify.py"))
connect, seed_user, Guard, Sessions = (
    _helpers["connect"], _helpers["seed_user"], _helpers["Guard"], _helpers["Sessions"],
)


def main() -> None:
    name = "ai03a07p03_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                system, user = "SYNTHETIC_PRIVATE_SYSTEM_TEXT", "SYNTHETIC_PRIVATE_USER_TEXT"
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Prompt Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Prompt Member", "NONE", member_token)
                    ids = [db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0] for _ in range(3)]
                    for ident in ids[1:]:
                        db.execute(
                            "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
                            "system_template,user_template,system_template_hash,user_template_hash,"
                            "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,"
                            "created_by) VALUES (%s,1,%s,%s,%s,%s,'schema.synthetic.v1',1,"
                            "'rag.synthetic.v1','provider.synthetic.v1',%s)",
                            (ident, system, user, hashlib.sha256(system.encode()).hexdigest(),
                             hashlib.sha256(user.encode()).hexdigest(), actor),
                        )
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                               "active_version_no=1,lock_version=1 WHERE prompt_template_id=%s", (ids[1],))
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='RETIRED',"
                               "active_version_no=1,lock_version=2 WHERE prompt_template_id=%s", (ids[2],))
                guard = Guard()
                service = PromptMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemyPromptMetadataRepository(),
                    cursors=PromptListCursorCodec(b"p" * 32),
                )
                router = create_ai_prompt_read_router(
                    sessions=Sessions(), prompts=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = "/api/v1/admin/ai/prompt-templates"
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.get(path).status_code == 404
                    assert default.get(f"{path}/{ids[1]}").status_code == 404
                with TestClient(create_app(ai_prompt_read_router=router),
                                base_url="http://localhost") as client:
                    headers = {"cookie": "plm_session=" + admin_token.hex()}
                    member = {"cookie": "plm_session=" + member_token.hex()}
                    first = client.get(path + "?page_size=2", headers=headers)
                    assert first.status_code == 200 and first.headers["cache-control"] == "no-store", first.text
                    cursor = first.json()["data"]["next_cursor"]
                    assert cursor and len(first.json()["data"]["items"]) == 2
                    second = client.get(path + "?page_size=2&cursor=" + cursor, headers=headers)
                    assert second.status_code == 200 and len(second.json()["data"]["items"]) == 1
                    items = first.json()["data"]["items"] + second.json()["data"]["items"]
                    assert {item["prompt_template_id"] for item in items} == {str(ident) for ident in ids}
                    by_id = {item["prompt_template_id"]: item for item in items}
                    assert by_id[str(ids[0])]["active_version_no"] is None
                    assert by_id[str(ids[1])]["active_version_no"] == 1
                    assert by_id[str(ids[2])]["active_version_no"] is None
                    assert by_id[str(ids[2])]["output_schema_ref"] is None
                    detail = client.get(f"{path}/{ids[1]}", headers=headers)
                    assert detail.status_code == 200 and detail.headers["etag"] == '"v1"'
                    assert detail.headers["x-trace-id"] == detail.json()["trace_id"]
                    assert system not in first.text + second.text + detail.text
                    assert user not in first.text + second.text + detail.text
                    assert client.get(path, headers=member).status_code == 404
                    assert client.get(f"{path}/{ids[1]}", headers=member).status_code == 404
                    assert client.get(path + "?page_size=3&cursor=" + cursor,
                                      headers=headers).status_code == 400
                    assert client.get(path + "?page_size=2&cursor=" + cursor,
                                      headers=member).status_code == 404
                    guard.enabled = False
                    assert client.get(path, headers=headers).status_code == 403
                    guard.enabled = True
                    with connect(name) as db:
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),"
                                   "revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 "
                                   "WHERE session_token_digest=%s", (hashlib.sha256(admin_token).digest(),))
                    assert client.get(path, headers=headers).status_code == 404
                print("PASS: optional Prompt HTTP/PG18 metadata, page/ETag, auth/License/revocation, no body")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
