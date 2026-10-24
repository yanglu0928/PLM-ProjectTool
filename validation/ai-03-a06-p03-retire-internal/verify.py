"""Disposable PG18 Prompt retirement proof without production trust or HTTP."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.retire_prompt_template import (
    PromptRetireError, PromptTemplateRetireService, RetirePromptTemplate,
)
from plm_assistant.modules.ai.infrastructure.prompt_retire_repository import SqlAlchemyPromptRetireRepository
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
    except PromptRetireError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai03a06p03_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Retire Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Retire Member", "NONE", member_token)
                    draft = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                    active = db.execute(
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
                        (active, system, user, hashlib.sha256(system.encode()).hexdigest(),
                         hashlib.sha256(user.encode()).hexdigest(), actor),
                    )
                    db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                               "active_version_no=1,lock_version=2 WHERE prompt_template_id=%s", (active,))
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, repository=SqlAlchemyPromptRetireRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = PromptTemplateRetireService(
                    **kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def retire(*, template_id=draft, expected=0, key=None,
                           token=admin_token, csrf=CSRF, target=service):
                    return target.retire(RetirePromptTemplate(
                        token, csrf, uuid.uuid4(), template_id, expected,
                        key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: retire(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: retire(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", retire)
                guard.enabled = True
                expect("AI_PROMPT_NOT_FOUND", lambda: retire(template_id=uuid.uuid4()))
                expect("CONFLICT_VERSION", lambda: retire(expected=1))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results").fetchone()[0] == 0
                first_key = str(uuid.uuid4())
                first = retire(key=first_key)
                assert first.prior_state == "DRAFT" and first.prior_active_version_no is None
                assert first.lock_version == 1 and first.etag == '"v1"'
                assert retire(key=first_key) == first
                expect("CONFLICT_IDEMPOTENCY", lambda: retire(key=first_key, expected=1))
                expect("AI_PROMPT_STATE_CONFLICT", lambda: retire(expected=1))

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda _: retire(
                        template_id=active, expected=2, key=concurrent_key,
                    ), range(2)))
                assert outcomes[0] == outcomes[1]
                assert outcomes[0].prior_state == "ACTIVE" and outcomes[0].prior_active_version_no == 1
                assert outcomes[0].lock_version == 3
                with connect(name) as db:
                    assert db.execute("SELECT template_state,active_version_no,lock_version FROM "
                                      "plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                      (active,)).fetchone() == ("RETIRED", 1, 3)
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results").fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROMPT_RETIRE'").fetchone()[0] == 2

                with connect(name) as db:
                    rollback = db.execute(
                        "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                        "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                    ).fetchone()[0]
                failed = PromptTemplateRetireService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_PROMPT_UNAVAILABLE", lambda: retire(
                    template_id=rollback, key=rollback_key, target=failed,
                ))
                recovered = retire(template_id=rollback, key=rollback_key)
                assert recovered.lock_version == 1
                assert retire(key=first_key) == first
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results").fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROMPT_RETIRE'").fetchone()[0] == 3
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: retire(key=first_key))
                print("PASS: DRAFT/ACTIVE retirement, admin/CSRF/License, idempotent concurrency/replay, Audit rollback, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
