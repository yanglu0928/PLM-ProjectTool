"""Disposable PostgreSQL 18 proof for CR-DOC-006 foundational schema."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.platform.infrastructure import configuration_orm, idempotency_orm, secret_orm  # noqa: F401
from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import user_orm, session_orm, login_rate_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import installation_orm, validation_orm, trusted_time_orm  # noqa: F401
from plm_assistant.modules.project.infrastructure import orm as project_orm  # noqa: F401
from plm_assistant.modules.document.infrastructure import orm as document_orm  # noqa: F401
from plm_assistant.modules.jobs.infrastructure import orm as job_orm  # noqa: F401


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def verify() -> None:
    name = "job_schema_" + uuid.uuid4().hex[:12]
    admin = psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    cfg = create_migration_config(url)
    try:
        command.upgrade(cfg, "20260925_0024")
        engine = create_engine(url)
        try:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES ('job-test','job-test','DEPLOYMENT_ADMIN')"))
            command.upgrade(cfg, "head")
            with engine.begin() as conn:
                assert conn.scalar(text("SELECT count(*) FROM plm.auth_users")) == 1
                differences = compare_metadata(MigrationContext.configure(conn, opts={"include_schemas": True, "compare_type": True, "compare_server_default": True, "include_name": lambda name, type_, parent: name == 'plm' if type_ == 'schema' else parent.get('schema_name') in (None, 'plm')}), Base.metadata)
                differences = [item for item in differences if not (item[0] == "remove_table" and item[1].name == "alembic_version")]
                assert not differences, differences
                job = conn.scalar(text("INSERT INTO plm.job_jobs(owner_module,job_type,scope,trace_id,payload_refs,idempotency_key,max_attempts) VALUES ('document','PARSE','GLOBAL','synthetic','{}'::jsonb,'once',3) RETURNING job_id"))
                event = conn.scalar(text("INSERT INTO plm.job_outbox_events(event_type,owner_module,scope,aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id) VALUES ('DOCUMENT_VERSION_COMMITTED','document','GLOBAL',:id,1,'{}'::jsonb,'once','synthetic') RETURNING event_id"), {"id": job})
                conn.execute(text("INSERT INTO plm.job_outbox_consumptions(event_id,consumer_id) VALUES (:id,'parser')"), {"id": event})
                for statement in (
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,trace_id,payload_refs,idempotency_key,max_attempts) VALUES ('document','PARSE','GLOBAL','synthetic','{}'::jsonb,'once',3)",
                    "INSERT INTO plm.job_outbox_consumptions(event_id,consumer_id) VALUES (:id,'parser')",
                ):
                    try:
                        with conn.begin_nested():
                            conn.execute(text(statement), {"id": event})
                    except Exception:
                        pass
                    else:
                        raise AssertionError("duplicate accepted")
            try:
                command.downgrade(cfg, "20260925_0024")
            except RuntimeError as exc:
                assert "history exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM plm.job_outbox_consumptions"))
                conn.execute(text("DELETE FROM plm.job_outbox_events"))
                conn.execute(text("DELETE FROM plm.job_jobs"))
            command.downgrade(cfg, "20260925_0024")
            command.upgrade(cfg, "head")
            print("PASS: existing-data upgrade, ORM parity, idempotency/consumer uniqueness, nonempty downgrade refusal, empty downgrade/re-upgrade")
        finally:
            engine.dispose()
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
