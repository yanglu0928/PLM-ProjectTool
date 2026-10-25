"""Disposable PG18 proof for internal DRAFT PromptTemplate create; no Prompt body."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_prompt_template import (
    CreatePromptTemplate, PromptTemplateCreateError, PromptTemplateCreateService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.infrastructure.prompt_create_repository import SqlAlchemyPromptCreateRepository
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


def expect(code: str, action) -> None:
    try:
        action()
    except PromptTemplateCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai03a03_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Prompt Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Prompt Member", "NONE", member_token)
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, repository=SqlAlchemyPromptCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = PromptTemplateCreateService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def create(*, token=admin_token, csrf=CSRF,
                           task_type=PromptTaskType.GAP_ANALYSIS, key=None, target=service):
                    return target.create_view(CreatePromptTemplate(
                        token, csrf, uuid.uuid4(), task_type, key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_templates").fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_CREATE'").fetchone()[0] == 0

                first_key = str(uuid.uuid4())
                first = create(key=first_key)
                assert first == create(key=first_key)
                expect("CONFLICT_IDEMPOTENCY", lambda: create(
                    key=first_key, task_type=PromptTaskType.SURVEY_GENERATE,
                ))
                with connect(name) as db:
                    assert db.execute("SELECT scope,template_state,active_version_no,lock_version "
                                      "FROM plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                      (first.prompt_template_id,)).fetchone() == ("DEPLOYMENT", "DRAFT", None, 0)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions").fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_CREATE' AND target_object_id=%s",
                                      (first.prompt_template_id,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                      "WHERE operation='V1_AI_PROMPT_CREATE'").fetchone()[0] == 1
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='RETIRED',lock_version=1 "
                               "WHERE prompt_template_id=%s", (first.prompt_template_id,))
                assert create(key=first_key) == first  # immutable first view, not current RETIRED state

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(key=concurrent_key), range(2)))
                assert results[0] == results[1] and results[0] != first

                failed = PromptTemplateCreateService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_PROMPT_UNAVAILABLE", lambda: create(key=rollback_key, target=failed))
                assert create(key=rollback_key).prompt_template_id not in (
                    first.prompt_template_id, results[0].prompt_template_id,
                )
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_templates").fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_PROMPT_CREATE'").fetchone()[0] == 3
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: create(key=first_key))
                print("PASS: admin/CSRF/License, DRAFT/no version, receipt/Audit, replay after RETIRED, conflict, concurrent replay, audit rollback, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
