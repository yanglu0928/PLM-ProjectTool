"""Disposable PG18 internal PromptVersion append proof with synthetic admission only."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, PromptVersionAppendError, PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
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


class SyntheticAdmission:
    enabled = False
    mismatch = False

    def approved_fingerprint(self, transaction: object, *, actor_id: uuid.UUID, draft) -> bytes | None:
        if not self.enabled:
            return None
        return b"x" * 32 if self.mismatch else draft.fingerprint


def expect(code: str, action) -> None:
    try:
        action()
    except PromptVersionAppendError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai03a04p02_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Version Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Version Member", "NONE", member_token)
                    template = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                    retired = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,template_state,created_by) "
                        "VALUES ('GAP_ANALYSIS','RETIRED',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                guard, admission = Guard(), SyntheticAdmission()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, admission=admission,
                    repository=SqlAlchemyPromptVersionRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = PromptVersionAppendService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def append(*, token=admin_token, csrf=CSRF, target=service,
                           template_id=template, expected=0, key=None, user="Question: {input}",
                           task_type=PromptTaskType.GAP_ANALYSIS):
                    return target.append(AppendPromptVersion(
                        token, csrf, uuid.uuid4(), template_id, task_type,
                        "Synthetic system: use {context}.", user,
                        "schema.synthetic.v1", 1, "rag.synthetic.v1",
                        "provider.synthetic.v1", expected, key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: append(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: append(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", append)
                guard.enabled = True
                expect("AI_PROMPT_CONTENT_UNAPPROVED", append)
                admission.enabled, admission.mismatch = True, True
                expect("AI_PROMPT_CONTENT_UNAPPROVED", append)
                admission.mismatch = False
                expect("AI_PROMPT_STATE_CONFLICT", lambda: append(template_id=retired))
                expect("AI_PROMPT_STATE_CONFLICT", lambda: append(
                    task_type=PromptTaskType.SURVEY_GENERATE,
                ))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions").fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_VERSION_CREATE'").fetchone()[0] == 0

                first_key = str(uuid.uuid4())
                first = append(key=first_key)
                assert first.version_no == 1 and first.lock_version == 1
                assert append(key=first_key) == first
                expect("CONFLICT_IDEMPOTENCY", lambda: append(key=first_key, user="Changed {input}"))
                expect("CONFLICT_VERSION", lambda: append(expected=0))
                second = append(expected=1, user="Second {input}")
                assert second.version_no == 2 and second.lock_version == 2
                assert append(key=first_key) == first
                with connect(name) as db:
                    assert db.execute("SELECT lock_version,active_version_no FROM plm.ai_prompt_templates "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone() == (2, None)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_version_create_results "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_VERSION_CREATE' AND target_object_id=%s",
                                      (template,)).fetchone()[0] == 2

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: append(
                        expected=2, user="Third {input}", key=concurrent_key,
                    ), range(2)))
                assert results[0] == results[1] and results[0].version_no == 3

                failed = PromptVersionAppendService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_PROMPT_UNAVAILABLE", lambda: append(
                    expected=3, user="Fourth {input}", key=rollback_key, target=failed,
                ))
                recovered = append(expected=3, user="Fourth {input}", key=rollback_key)
                assert recovered.version_no == 4
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions "
                                      "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 4
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='RETIRED' "
                               "WHERE prompt_template_id=%s", (template,))
                assert append(key=first_key) == first
                expect("AI_PROMPT_STATE_CONFLICT", lambda: append(expected=4))
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: append(key=first_key))
                print("PASS: admission fail-closed, admin/CSRF/License, immutable v1-v4, conditional lock, replay after later version/retire, concurrent key, Audit rollback, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
