"""Isolated PostgreSQL 18 acceptance for same-transaction AuditService append."""

from __future__ import annotations

import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def event() -> AuditEventDraft:
    return AuditEventDraft(
        trace_id=uuid.uuid4(), event_scope="DEPLOYMENT", target_project_id=None,
        actor_type="USER", actor_id=uuid.uuid4(), original_actor_id=None,
        actor_hint_digest=None, action="CONFIG_CREATE", outcome="SUCCESS",
        target_owner_module="platform", target_object_type="PLT-01",
        target_object_id=uuid.uuid4(),
    )


def main() -> None:
    name = f"aud01a02_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise RuntimeError("probe database already exists")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url(name)), "head")
            runtime = create_database_runtime(url(name))
            try:
                service = AuditService(SqlAlchemyAuditRepository())
                with runtime.unit_of_work() as tx:
                    tx.session.execute(text("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('audit.commit')"))
                    event_id = service.append(tx, event())
                    assert event_id.version == 7
                    with conn(name) as observer:
                        assert observer.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
                    tx.commit()
                with conn(name) as observer:
                    assert observer.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                    assert observer.execute("SELECT count(*) FROM plm.plt_system_configurations").fetchone()[0] == 1

                try:
                    with runtime.unit_of_work() as tx:
                        tx.session.execute(text("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('audit.rollback')"))
                        service.append(tx, event())
                        raise RuntimeError("synthetic business failure")
                except RuntimeError as exc:
                    assert str(exc) == "synthetic business failure"
                with conn(name) as observer:
                    assert observer.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                    assert observer.execute("SELECT count(*) FROM plm.plt_system_configurations").fetchone()[0] == 1

                with runtime.unit_of_work() as tx:
                    service.append(tx, event())
                    # No explicit commit: UoW must roll back the audit insert.
                with conn(name) as observer:
                    assert observer.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
            finally:
                runtime.dispose()
            print("PASS: same-transaction commit visibility, business+audit rollback, implicit rollback, UUIDv7 event ID")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
