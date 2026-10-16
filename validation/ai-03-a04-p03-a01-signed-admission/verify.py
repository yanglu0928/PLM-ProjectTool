"""Disposable PG18 signed Prompt admission proof; ephemeral key only."""

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
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, PromptVersionAppendError, PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.prompt_version_repository import SqlAlchemyPromptVersionRepository
from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import SignedPromptAdmission
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, Guard, CSRF = (
    _helpers["connect"], _helpers["seed_user"], _helpers["Guard"], _helpers["CSRF"],
)


def main() -> None:
    name = "ai03a04p03_" + uuid.uuid4().hex[:12]
    token = b"a" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Signed Prompt Admin", "DEPLOYMENT_ADMIN", token)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                system, user = "Synthetic system: cite {context}.", "Synthetic question {input}"
                draft = PromptVersionDraft(
                    template, PromptTaskType.GAP_ANALYSIS, system, user,
                    "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
                )
                payload = {
                    "generation": 1, "reviewer_ref": "developer.synthetic",
                    "reviewed_at": "2026-10-02T00:00:00Z",
                    "entries": [{"prompt_template_id": str(template),
                                 "task_type": "GAP_ANALYSIS",
                                 "fingerprint": draft.fingerprint.hex()}],
                }
                private = Ed25519PrivateKey.generate()
                canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode()
                signature = private.sign(b"PLM-PROMPT-ADMISSION-V1\n" + canonical)
                document = json.dumps({
                    "format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                    "signature": base64.b64encode(signature).decode(),
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
                admission = SignedPromptAdmission(
                    public_key=private.public_key().public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw,
                    ),
                    signed_manifest=document,
                    expected_manifest_sha256=hashlib.sha256(document).digest(),
                )
                service = PromptVersionAppendService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=Guard(),
                    admission=admission, repository=SqlAlchemyPromptVersionRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def append(user_text: str, key: str) -> object:
                    return service.append(AppendPromptVersion(
                        token, CSRF, uuid.uuid4(), template, PromptTaskType.GAP_ANALYSIS,
                        system, user_text, "schema.synthetic.v1", 1,
                        "rag.synthetic.v1", "provider.synthetic.v1", 0, key,
                    ))

                try:
                    append("Changed {input}", str(uuid.uuid4()))
                except PromptVersionAppendError as exc:
                    assert exc.code == "AI_PROMPT_CONTENT_UNAPPROVED", exc.code
                else:
                    raise AssertionError("unlisted content accepted")
                key = str(uuid.uuid4())
                result = append(user, key)
                assert result.version_no == 1
                assert append(user, key) == result
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_VERSION_CREATE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 1
                print("PASS: ephemeral signed/pinned manifest permits only exact listed digest through PG18 atomic append/replay; changed content denied")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
