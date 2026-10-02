"""Disposable PG18/HTTP Prompt retirement proof; no production routing."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.retire_prompt_template import create_ai_prompt_retire_router
from plm_assistant.modules.ai.application.retire_prompt_template import PromptTemplateRetireService
from plm_assistant.modules.ai.infrastructure.prompt_retire_repository import SqlAlchemyPromptRetireRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_base = Path(__file__).resolve().parents[1]
_helpers = runpy.run_path(str(_base / "ai-02-a02-model-create" / "verify.py"))
_http_helpers = runpy.run_path(str(_base / "ai-03-a04-p03-a03-p02-http-pg" / "verify.py"))
connect, seed_user, Guard = _helpers["connect"], _helpers["seed_user"], _helpers["Guard"]
Sessions = _http_helpers["Sessions"]


def main() -> None:
    name = "ai03a06http_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Prompt Retire HTTP Admin",
                                      "DEPLOYMENT_ADMIN", b"a" * 32)
                    seed_user(db, "Synthetic Prompt Retire HTTP Member", "NONE", b"m" * 32)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                    system, user = "Synthetic system", "Synthetic {input}"
                    db.execute(
                        "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
                        "user_template,system_template_hash,user_template_hash,output_schema_ref,schema_version,"
                        "rag_policy_ref,provider_policy_ref,created_by) VALUES "
                        "(%s,1,%s,%s,%s,%s,'schema.synthetic.v1',1,'rag.synthetic.v1',"
                        "'provider.synthetic.v1',%s)",
                        (template, system, user, hashlib.sha256(system.encode()).hexdigest(),
                         hashlib.sha256(user.encode()).hexdigest(), actor),
                    )
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                               "active_version_no=1,lock_version=2 WHERE prompt_template_id=%s", (template,))
                guard = Guard()
                service = PromptTemplateRetireService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    repository=SqlAlchemyPromptRetireRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_prompt_retire_router(
                    sessions=Sessions(), retirements=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                path = f"/api/v1/admin/ai/prompt-templates/{template}:retire"
                headers = {"cookie": "plm_session=" + "61" * 32,
                           "x-csrf-token": "63" * 32,
                           "origin": "https://plm.example.test", "if-match": '"v2"',
                           "idempotency-key": str(uuid.uuid4())}
                with TestClient(create_app(), base_url="https://plm.example.test") as default:
                    assert default.post(path, json={}, headers=headers).status_code == 404
                with TestClient(create_app(ai_prompt_retire_router=router),
                                base_url="https://plm.example.test") as client:
                    member = client.post(path, json={}, headers={
                        **headers, "cookie": "plm_session=" + "6d" * 32,
                        "idempotency-key": str(uuid.uuid4()),
                    })
                    assert member.status_code == 404, member.text
                    unknown = client.post(
                        path.replace(str(template), str(uuid.uuid4())), json={},
                        headers={**headers, "idempotency-key": str(uuid.uuid4())},
                    )
                    assert unknown.status_code == 404, unknown.text
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results").fetchone()[0] == 0
                    first = client.post(path, json={}, headers=headers)
                    assert first.status_code == 200, first.text
                    assert first.headers["etag"] == '"v3"'
                    assert first.json()["data"] == {
                        "prompt_template_id": str(template), "state": "RETIRED", "etag": '"v3"',
                    }
                    assert system not in first.text and user not in first.text
                    replay = client.post(path, json={}, headers=headers)
                    assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
                    assert replay.json()["trace_id"] != first.json()["trace_id"]
                    conflict = client.post(path, json={}, headers={
                        **headers, "idempotency-key": str(uuid.uuid4()),
                    })
                    assert conflict.status_code == 409, conflict.text
                    guard.enabled = False
                    assert client.post(path, json={}, headers=headers).status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT template_state,active_version_no,lock_version FROM "
                                      "plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                      (template,)).fetchone() == ("RETIRED", 1, 3)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                                      "'AI_PROMPT_RETIRE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                      "WHERE operation='V1_AI_PROMPT_RETIRE'").fetchone()[0] == 1
                print("PASS: Win11 PG18 retirement HTTP default/member 404, 200/replay/409/license; one state/audit/result/receipt")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
