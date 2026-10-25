"""Disposable PG18 Prompt activation proof; admission is synthetic, not release trust."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.activate_prompt_version import (
    ActivatePromptVersion, PromptActivationError, PromptVersionActivationService,
)
from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.infrastructure.prompt_activation_repository import SqlAlchemyPromptActivationRepository
from plm_assistant.modules.ai.infrastructure.prompt_version_repository import SqlAlchemyPromptVersionRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = _helpers["connect"], _helpers["seed_user"]
Guard, FailedAudit, CSRF = _helpers["Guard"], _helpers["FailedAudit"], _helpers["CSRF"]


class Admission:
    allowed: set[bytes]

    def __init__(self) -> None:
        self.allowed = set()

    def approved_fingerprint(self, transaction: object, *, actor_id: uuid.UUID, draft) -> bytes | None:
        return draft.fingerprint if draft.fingerprint in self.allowed else None


def expect(code: str, action) -> None:
    try:
        action()
    except PromptActivationError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai03a05p03_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Activation Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Activation Member", "NONE", member_token)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                    retired = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,template_state,created_by) "
                        "VALUES ('GAP_ANALYSIS','RETIRED',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                guard, admission = Guard(), Admission()
                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, admission=admission,
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                append = PromptVersionAppendService(
                    **common, repository=SqlAlchemyPromptVersionRepository(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )
                service = PromptVersionActivationService(
                    **common, repository=SqlAlchemyPromptActivationRepository(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def add(text: str, expected: int, template_id=template):
                    from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
                    draft = PromptVersionDraft(
                        template_id, PromptTaskType.GAP_ANALYSIS,
                        "Synthetic system: use {context}.", text,
                        "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
                    )
                    admission.allowed.add(draft.fingerprint)
                    return append.append(AppendPromptVersion(
                        admin_token, CSRF, uuid.uuid4(), template_id, PromptTaskType.GAP_ANALYSIS,
                        draft.system_template, draft.user_template, draft.output_schema_ref,
                        draft.schema_version, draft.rag_policy_ref, draft.provider_policy_ref,
                        expected, str(uuid.uuid4()),
                    )), draft

                v1, draft1 = add("First {input}", 0)
                v2, draft2 = add("Second {input}", 1)
                v3, draft3 = add("Unreviewed {input}", 2)
                admission.allowed.remove(draft3.fingerprint)
                assert (v1.version_no, v2.version_no, v3.version_no) == (1, 2, 3)

                def activate(*, version=1, expected=3, key=None, token=admin_token,
                             csrf=CSRF, target=service, template_id=template):
                    return target.activate(ActivatePromptVersion(
                        token, csrf, uuid.uuid4(), template_id, version, expected,
                        key or str(uuid.uuid4()),
                    ))

                guard.enabled = True
                expect("AUTH_ACCESS_DENIED", lambda: activate(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: activate(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", activate)
                guard.enabled = True
                expect("AI_PROMPT_CONTENT_UNAPPROVED", lambda: activate(version=3))
                expect("AI_PROMPT_VERSION_NOT_FOUND", lambda: activate(version=4))
                expect("AI_PROMPT_NOT_FOUND", lambda: activate(template_id=uuid.uuid4()))
                expect("AI_PROMPT_STATE_CONFLICT", lambda: activate(template_id=retired, expected=0))
                with connect(name) as db:
                    assert db.execute("SELECT template_state,active_version_no,lock_version FROM "
                                      "plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                      (template,)).fetchone() == ("DRAFT", None, 3)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_activation_results").fetchone()[0] == 0

                first_key = str(uuid.uuid4())
                first = activate(key=first_key)
                assert first.version_no == 1 and first.lock_version == 4 and first.etag == '"v4"'
                assert activate(key=first_key) == first
                expect("CONFLICT_IDEMPOTENCY", lambda: activate(key=first_key, version=2))
                expect("CONFLICT_VERSION", lambda: activate(version=2, expected=3))
                expect("AI_PROMPT_STATE_CONFLICT", lambda: activate(version=1, expected=4))

                # Two different keys compete for the same root version; only one can commit.
                def compete(version: int):
                    try:
                        return activate(version=version, expected=4)
                    except PromptActivationError as error:
                        return error.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(compete, (1, 2)))
                assert sum(isinstance(item, str) for item in outcomes) == 1
                assert any(item in ("AI_PROMPT_STATE_CONFLICT", "CONFLICT_VERSION") for item in outcomes if isinstance(item, str))
                assert any(getattr(item, "version_no", None) == 2 for item in outcomes)
                assert activate(key=first_key) == first

                failed = PromptVersionActivationService(
                    **common, repository=SqlAlchemyPromptActivationRepository(), audit=FailedAudit(),
                )
                rollback_key = str(uuid.uuid4())
                expect("AI_PROMPT_UNAVAILABLE", lambda: activate(
                    version=1, expected=5, key=rollback_key, target=failed,
                ))
                recovered = activate(version=1, expected=5, key=rollback_key)
                assert recovered.lock_version == 6
                with connect(name) as db:
                    assert db.execute("SELECT template_state,active_version_no,lock_version FROM "
                                      "plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                      (template,)).fetchone() == ("ACTIVE", 1, 6)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_activation_results "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action="
                                      "'AI_PROMPT_VERSION_ACTIVATE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 3
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='RETIRED' "
                               "WHERE prompt_template_id=%s", (template,))
                assert activate(key=first_key) == first
                expect("AI_PROMPT_STATE_CONFLICT", lambda: activate(version=2, expected=6))
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: activate(key=first_key))
                print("PASS: admission, admin/CSRF/License, activation/switch, concurrency, immutable replay, rollback, retirement, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
