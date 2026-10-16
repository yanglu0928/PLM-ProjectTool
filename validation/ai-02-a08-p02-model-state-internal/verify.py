"""Disposable PG18 proof of authorized non-AVAILABLE AIModel state commands."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.change_model_state import (
    AIModelStateError, AIModelStateService, ChangeAIModelState,
)
from plm_assistant.modules.ai.infrastructure.model_state_repository import SqlAlchemyAIModelStateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, seed_provider = (
    _helpers["connect"], _helpers["seed_user"], _helpers["seed_provider"],
)
Guard, FailedAudit = _helpers["Guard"], _helpers["FailedAudit"]


def expect(code: str, action) -> None:
    try:
        action()
    except AIModelStateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai02a08p02_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Model State Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Model State Member", "NONE", member_token)
                    provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                             can_structured=False)
                    models = [db.execute(
                        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                        "model_revision,embedding_dimension,created_by) "
                        "VALUES (%s,%s,'EMBEDDING','PROVIDER_MANAGED',1024,%s) "
                        "RETURNING ai_model_id", (provider, f"embed-state-{n}", actor),
                    ).fetchone()[0] for n in range(3)]
                    db.execute("UPDATE plm.ai_models SET model_state='AVAILABLE' "
                               "WHERE ai_model_id=%s", (models[1],))
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard,
                    repository=SqlAlchemyAIModelStateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = AIModelStateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def change(model_id, operation, version, *, key=None, token=admin_token,
                           csrf=b"c" * 32, target=service):
                    return target.change(ChangeAIModelState(
                        token, csrf, uuid.uuid4(), model_id, version,
                        operation, key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: change(models[0], "RETIRE", 0,
                                                             token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: change(models[0], "RETIRE", 0,
                                                             csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: change(models[0], "RETIRE", 0))
                guard.enabled = True
                expect("VALIDATION_FAILED", lambda: change(models[0], "AVAILABLE", 0))
                expect("CONFLICT_STATE", lambda: change(models[0], "SUSPEND", 0))
                expect("RESOURCE_NOT_FOUND", lambda: change(uuid.uuid4(), "RETIRE", 0))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 0

                retire_key = str(uuid.uuid4())
                retired = change(models[0], "RETIRE", 0, key=retire_key)
                assert retired.state == "RETIRED" and retired.etag == '"v1"'
                assert change(models[0], "RETIRE", 0, key=retire_key) == retired
                expect("CONFLICT_IDEMPOTENCY", lambda: change(models[1], "RETIRE", 0,
                                                                key=retire_key))
                expect("CONFLICT_VERSION", lambda: change(models[0], "RETIRE", 0))
                expect("CONFLICT_STATE", lambda: change(models[0], "RETIRE", 1))

                suspend_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(
                        lambda _: change(models[1], "SUSPEND", 0, key=suspend_key), range(2),
                    ))
                assert results[0] == results[1] and results[0].state == "SUSPENDED"
                assert results[0].etag == '"v1"'
                second = change(models[1], "RETIRE", 1, key=suspend_key)
                assert second.state == "RETIRED" and second.etag == '"v2"'
                assert change(models[1], "SUSPEND", 0, key=suspend_key) == results[0]
                with connect(name) as db:
                    assert db.execute("SELECT model_state,lock_version FROM plm.ai_models "
                                      "WHERE ai_model_id=%s", (models[1],)).fetchone() == ("RETIRED", 2)
                    assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action IN "
                                      "('AI_MODEL_SUSPENDED','AI_MODEL_RETIRED')").fetchone()[0] == 3

                failed = AIModelStateService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_MODEL_UNAVAILABLE", lambda: change(models[2], "RETIRE", 0,
                                                                key=rollback_key, target=failed))
                with connect(name) as db:
                    assert db.execute("SELECT model_state,lock_version FROM plm.ai_models "
                                      "WHERE ai_model_id=%s", (models[2],)).fetchone() == ("SUSPENDED", 0)
                    assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 3
                assert change(models[2], "RETIRE", 0, key=rollback_key).state == "RETIRED"
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: change(models[0], "RETIRE", 0,
                                                             key=retire_key))
                print("PASS: Model SUSPEND/RETIRE auth/license/version, concurrent replay, immutable result, Audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
