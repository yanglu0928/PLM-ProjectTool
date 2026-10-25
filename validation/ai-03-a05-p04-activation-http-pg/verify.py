"""Disposable PG18/HTTP Prompt activation proof with ephemeral signed admission."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.activate_prompt_version import create_ai_prompt_activation_router
from plm_assistant.modules.ai.application.activate_prompt_version import PromptVersionActivationService
from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.prompt_activation_repository import SqlAlchemyPromptActivationRepository
from plm_assistant.modules.ai.infrastructure.prompt_version_repository import SqlAlchemyPromptVersionRepository
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
connect, seed_user, Guard, CSRF = (
    _helpers["connect"], _helpers["seed_user"], _helpers["Guard"], _helpers["CSRF"],
)
Sessions, admission_for = _http_helpers["Sessions"], _http_helpers["_admission"]


def main() -> None:
    name = "ai03a05http_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Prompt Activate HTTP Admin",
                                      "DEPLOYMENT_ADMIN", b"a" * 32)
                    seed_user(db, "Synthetic Prompt Activate HTTP Member", "NONE", b"m" * 32)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                draft = PromptVersionDraft(
                    template, PromptTaskType.GAP_ANALYSIS,
                    "Synthetic system: cite {context}.", "Synthetic question {input}",
                    "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
                )
                guard, admission = Guard(), admission_for(draft)
                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, admission=admission,
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                append = PromptVersionAppendService(
                    **common, repository=SqlAlchemyPromptVersionRepository(),
                )
                created = append.append(AppendPromptVersion(
                    b"a" * 32, CSRF, uuid.uuid4(), template, PromptTaskType.GAP_ANALYSIS,
                    draft.system_template, draft.user_template, draft.output_schema_ref,
                    draft.schema_version, draft.rag_policy_ref, draft.provider_policy_ref,
                    0, str(uuid.uuid4()),
                ))
                assert created.version_no == 1 and created.lock_version == 1
                service = PromptVersionActivationService(
                    **common, repository=SqlAlchemyPromptActivationRepository(),
                )
                router = create_ai_prompt_activation_router(
                    sessions=Sessions(), activations=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                path = f"/api/v1/admin/ai/prompt-templates/{template}/versions/1:activate"
                headers = {"cookie": "plm_session=" + "61" * 32,
                           "x-csrf-token": "63" * 32,
                           "origin": "https://plm.example.test", "if-match": '"v1"',
                           "idempotency-key": str(uuid.uuid4())}
                with TestClient(create_app(), base_url="https://plm.example.test") as default:
                    assert default.post(path, json={}, headers=headers).status_code == 404
                with TestClient(create_app(ai_prompt_activation_router=router),
                                base_url="https://plm.example.test") as client:
                    member = client.post(path, json={}, headers={
                        **headers, "cookie": "plm_session=" + "6d" * 32,
                        "idempotency-key": str(uuid.uuid4()),
                    })
                    assert member.status_code == 404, member.text
                    unknown = client.post(path.replace("/1:activate", "/2:activate"), json={},
                                          headers={**headers, "idempotency-key": str(uuid.uuid4())})
                    assert unknown.status_code == 404, unknown.text
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_prompt_activation_results").fetchone()[0] == 0
                    first = client.post(path, json={}, headers=headers)
                    assert first.status_code == 200, first.text
                    assert first.headers["etag"] == '"v2"'
                    assert first.json()["data"] == {
                        "prompt_template_id": str(template), "version_no": 1,
                        "state": "ACTIVE", "etag": '"v2"',
                    }
                    assert draft.system_template not in first.text and draft.user_template not in first.text
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
                                      (template,)).fetchone() == ("ACTIVE", 1, 2)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_activation_results "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                                      "'AI_PROMPT_VERSION_ACTIVATE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                      "WHERE operation='V1_AI_PROMPT_ACTIVATE_VERSION'").fetchone()[0] == 1
                print("PASS: Win11 PG18 synthetic HTTP activation default/member 404, 200/replay/409/license; one state/audit/result/receipt")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
