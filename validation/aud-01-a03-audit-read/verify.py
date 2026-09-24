"""Isolated PostgreSQL 18 audit read-scope and keyset acceptance."""

from __future__ import annotations

import uuid
from dataclasses import fields
from datetime import datetime, timedelta, timezone

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import (
    AuditAccessDenied, AuditEventDraft, AuditEventView, AuditQueryService, AuditSearch, AuditService,
)
from plm_assistant.modules.audit.infrastructure.audit_read_repository import SqlAlchemyAuditReadRepository
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class Access:
    def can_read_project(self, transaction, principal, project_id):
        return project_id in principal["projects"]

    def can_read_deployment(self, transaction, principal):
        return principal["deployment_admin"] is True


def event(project_id: uuid.UUID | None, action: str) -> AuditEventDraft:
    return AuditEventDraft(
        trace_id=uuid.uuid4(), event_scope="PROJECT" if project_id else "DEPLOYMENT",
        target_project_id=project_id, actor_type="USER", actor_id=uuid.uuid4(),
        original_actor_id=None, actor_hint_digest=None, action=action, outcome="SUCCESS",
        target_owner_module="document", target_object_type="DOC-01", target_object_id=uuid.uuid4(),
    )


def main() -> None:
    name = f"aud01a03_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise RuntimeError("probe database already exists")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url(name)), "head")
            runtime = create_database_runtime(url(name))
            try:
                writer = AuditService(SqlAlchemyAuditRepository())
                reader = AuditQueryService(access=Access(), repository=SqlAlchemyAuditReadRepository())
                project_a, project_b = uuid.uuid4(), uuid.uuid4()
                with runtime.unit_of_work() as tx:
                    ids_a = [writer.append(tx, event(project_a, "CREATE")) for _ in range(3)]
                    id_b = writer.append(tx, event(project_b, "CREATE"))
                    id_deployment = writer.append(tx, event(None, "LOGIN"))
                    tx.commit()
                now = datetime.now(timezone.utc)
                query = AuditSearch(start_at=now - timedelta(days=1), end_at=now + timedelta(days=1), page_size=1)
                member = {"projects": {project_a}, "deployment_admin": False}
                outsider = {"projects": set(), "deployment_admin": False}
                admin_principal = {"projects": set(), "deployment_admin": True}
                with runtime.unit_of_work() as tx:
                    first = reader.list_project(tx, member, project_a, query)
                    assert first.has_more and len(first.items) == 1 and first.next_position is not None
                    seen = [first.items[0].audit_event_id]
                    position = first.next_position
                    while position is not None:
                        page = reader.list_project(tx, member, project_a, AuditSearch(
                            start_at=query.start_at, end_at=query.end_at, page_size=1, after=position,
                        ))
                        seen.extend(item.audit_event_id for item in page.items)
                        position = page.next_position
                    assert set(seen) == set(ids_a) and len(seen) == 3
                    assert reader.get_project(tx, member, project_a, id_b) is None
                    assert reader.get_project(tx, member, project_a, id_deployment) is None
                    assert reader.get_project(tx, member, project_a, ids_a[0]).target_project_id == project_a
                    assert reader.list_project(tx, member, project_a, AuditSearch(
                        start_at=query.start_at, end_at=query.end_at, action="LOGIN",
                    )).items == ()
                    try:
                        reader.list_project(tx, outsider, project_a, query)
                    except AuditAccessDenied:
                        pass
                    else:
                        raise AssertionError("unauthorized project list accepted")
                    try:
                        reader.get_project(tx, admin_principal, project_a, ids_a[0])
                    except AuditAccessDenied:
                        pass
                    else:
                        raise AssertionError("deployment admin bypassed project membership")
                    deployment = reader.list_deployment(tx, admin_principal, query)
                    assert [item.audit_event_id for item in deployment.items] == [id_deployment]
                    assert reader.get_deployment(tx, admin_principal, ids_a[0]) is None
                    assert reader.get_deployment(tx, admin_principal, id_deployment) is not None
                    assert "actor_hint_digest" not in {field.name for field in fields(AuditEventView)}
                    try:
                        reader.list_deployment(tx, member, query)
                    except AuditAccessDenied:
                        pass
                    else:
                        raise AssertionError("ordinary member read deployment audit")
            finally:
                runtime.dispose()
            print("PASS: authorized keyset page, project isolation, deployment-only admin read, denied before query, safe projection")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
