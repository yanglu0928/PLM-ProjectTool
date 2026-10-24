"""Disposable PG18/HTTP PromptVersion POST proof with ephemeral signed admission."""

from __future__ import annotations

import base64
import hashlib
import json
import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_prompt_version import create_ai_prompt_version_router
from plm_assistant.modules.ai.application.append_prompt_version import PromptVersionAppendService
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.packaged_prompt_admission import PackagedPromptAdmission
from plm_assistant.modules.ai.infrastructure.prompt_version_repository import SqlAlchemyPromptVersionRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, Guard, CSRF = (
    _helpers["connect"], _helpers["seed_user"], _helpers["Guard"], _helpers["CSRF"],
)


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if token not in (b"a" * 32, b"m" * 32) or csrf_token != CSRF or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def _admission(draft: PromptVersionDraft) -> PackagedPromptAdmission:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    payload = {"generation": 1, "reviewer_ref": "developer.synthetic",
               "reviewed_at": "2026-10-02T00:00:00Z",
               "entries": [{"prompt_template_id": str(draft.prompt_template_id),
                            "task_type": draft.task_type.value,
                            "fingerprint": draft.fingerprint.hex()}]}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode()
    signed = json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                         "signature": base64.b64encode(
                             private.sign(b"PLM-PROMPT-ADMISSION-V1\n" + canonical),
                         ).decode()}, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode()
    release = json.dumps({
        "schema_version": "plm.prompt-admission-release.v1",
        "key_ref": "plm-prompt-admission-release-v1",
        "public_key": base64.b64encode(public).decode(),
        "manifest_sha256": hashlib.sha256(signed).hexdigest(), "generation": 1,
    }, sort_keys=True, separators=(",", ":")).encode()
    return PackagedPromptAdmission(read_release=lambda: release,
                                   read_signed_manifest=lambda: signed)


def main() -> None:
    name = "ai03a04http_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Prompt HTTP Admin", "DEPLOYMENT_ADMIN", b"a" * 32)
                    seed_user(db, "Synthetic Prompt HTTP Member", "NONE", b"m" * 32)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                system, user = "Synthetic system: cite {context}.", "Synthetic question {input}"
                draft = PromptVersionDraft(
                    template, PromptTaskType.GAP_ANALYSIS, system, user,
                    "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
                )
                guard = Guard()
                service = PromptVersionAppendService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    admission=_admission(draft),
                    repository=SqlAlchemyPromptVersionRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_prompt_version_router(
                    sessions=Sessions(), versions=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                )
                path = f"/api/v1/admin/ai/prompt-templates/{template}/versions"
                headers = {"cookie": "plm_session=" + "61" * 32,
                           "x-csrf-token": "63" * 32,
                           "origin": "https://plm.example.test", "if-match": '"v0"',
                           "idempotency-key": str(uuid.uuid4())}
                body = {"task_type": "GAP_ANALYSIS", "system_template": system,
                        "user_template": user, "output_schema_ref": "schema.synthetic.v1",
                        "schema_version": 1, "rag_policy_ref": "rag.synthetic.v1",
                        "provider_policy_ref": "provider.synthetic.v1"}
                with TestClient(create_app(), base_url="https://plm.example.test") as default:
                    assert default.post(path, json=body, headers=headers).status_code == 404
                with TestClient(create_app(ai_prompt_version_router=router),
                                base_url="https://plm.example.test") as client:
                    member = client.post(
                        path, json=body,
                        headers={**headers, "cookie": "plm_session=" + "6d" * 32,
                                 "idempotency-key": str(uuid.uuid4())},
                    )
                    assert member.status_code == 404, member.text
                    denied = client.post(path, json={**body, "user_template": "Unlisted {input}"},
                                         headers={**headers, "idempotency-key": str(uuid.uuid4())})
                    assert denied.status_code == 422, denied.text
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions").fetchone()[0] == 0
                        assert db.execute("SELECT count(*) FROM plm.aud_events "
                                          "WHERE action='AI_PROMPT_VERSION_CREATE'").fetchone()[0] == 0
                    first = client.post(path, json=body, headers=headers)
                    assert first.status_code == 201, first.text
                    assert first.headers["etag"] == '"v1"'
                    assert first.json()["data"]["version_no"] == 1
                    assert user not in first.text and system not in first.text
                    replay = client.post(path, json=body, headers=headers)
                    assert replay.status_code == 201, replay.text
                    assert replay.json()["data"] == first.json()["data"]
                    assert replay.json()["trace_id"] != first.json()["trace_id"]
                    conflict = client.post(path, json={**body, "user_template": "Unlisted {input}"},
                                           headers=headers)
                    assert conflict.status_code == 409, conflict.text
                    guard.enabled = False
                    assert client.post(path, json=body, headers=headers).status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_VERSION_CREATE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                      "WHERE operation='V1_AI_PROMPT_CREATE_VERSION'").fetchone()[0] == 1
                print("PASS: Win11 PG18 synthetic HTTP PromptVersion default/member 404, unlisted 422, 201/replay/409/license; one version/audit/receipt")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
