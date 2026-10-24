"""Disposable PG18 proof for CR-PAR-002 Parser cancellation snapshot migration."""

from __future__ import annotations

import os
import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import inspect, create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.infrastructure.orm import parse_cancel_versions
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def run():
    name = "par_cancel_schema_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "head")
            command.downgrade(config, "20260927_0049")
            command.upgrade(config, "20260927_0049")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                                   "VALUES ('Parse cancel','parse cancel') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                                     "name,created_by) VALUES ('PCV','pcv','Parse cancel',%s) "
                                     "RETURNING project_id", (actor,)).fetchone()[0]
                job = db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                                 "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) "
                                 "VALUES ('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,%s,3) "
                                 "RETURNING job_id", (project,actor,str(uuid.uuid4()),
                                 Jsonb({"document_id":str(uuid.uuid4()),"document_version_id":str(uuid.uuid4())}),
                                 str(uuid.uuid4()))).fetchone()[0]
                baseline = tuple(db.execute("SELECT job_id,state,lock_version FROM plm.job_jobs"))
            command.upgrade(config, "head")
            with connect(name) as db:
                assert tuple(db.execute("SELECT job_id,state,lock_version FROM plm.job_jobs")) == baseline
                assert db.execute("SELECT count(*) FROM plm.job_parse_cancel_versions").fetchone()[0] == 0
            command.downgrade(config, "20260927_0049")
            command.upgrade(config, "head")
            engine = create_engine(url)
            try:
                with engine.connect() as conn:
                    columns = inspect(conn).get_columns(parse_cancel_versions.name, schema="plm")
                    assert set(c["name"] for c in columns) == set(parse_cancel_versions.c.keys())
                    assert all(not c["nullable"] for c in columns)
                    assert str(next(c["type"] for c in columns if c["name"] == "lock_version")) == "BIGINT"
            finally:
                engine.dispose()
            with connect(name) as db:
                def event(action, before, after, *, target=job, scope_project=project):
                    return db.execute("INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,"
                        "actor_type,actor_id,action,outcome,target_owner_module,target_object_type,"
                        "target_object_id,reason_code,before_state,after_state) "
                        "VALUES (%s,'PROJECT',%s,'USER',%s,%s,'SUCCESS','jobs','JOB-01',%s,"
                        "'USER_REQUESTED',%s,%s) RETURNING audit_event_id",
                        (uuid.uuid4(),scope_project,actor,action,target,before,after)).fetchone()[0]
                valid = event("DOCUMENT_PARSE_CANCEL_REQUESTED", "PENDING", "CANCELLED")
                db.execute("INSERT INTO plm.job_parse_cancel_versions(audit_event_id,lock_version) "
                           "VALUES (%s,2)", (valid,))
                def reject(statement, params=()):
                    before = tuple(db.execute("SELECT * FROM plm.job_parse_cancel_versions"))
                    try:
                        db.execute(statement, params)
                    except psycopg.Error:
                        pass
                    else:
                        raise AssertionError("invalid history write accepted")
                    assert tuple(db.execute("SELECT * FROM plm.job_parse_cancel_versions")) == before
                reject("UPDATE plm.job_parse_cancel_versions SET lock_version=3")
                reject("DELETE FROM plm.job_parse_cancel_versions")
                reject("TRUNCATE plm.job_parse_cancel_versions")
                reject("INSERT INTO plm.job_parse_cancel_versions VALUES (%s,2)", (valid,))
                reject("INSERT INTO plm.job_parse_cancel_versions VALUES (%s,-1)",
                       (event("DOCUMENT_PARSE_CANCEL_CHECKED","FAILED","FAILED"),))
                reject("INSERT INTO plm.job_parse_cancel_versions VALUES (%s,1)",
                       (event("DOCUMENT_PARSE_CANCEL_REQUESTED","SUCCEEDED","CANCELLED"),))
                reject("INSERT INTO plm.job_parse_cancel_versions VALUES (%s,1)",
                       (event("DOCUMENT_PARSE_CANCEL_REQUESTED","RUNNING","CANCELLED"),))
                assert db.execute("SELECT lock_version FROM plm.job_parse_cancel_versions "
                                  "WHERE audit_event_id=%s", (valid,)).fetchone()[0] == 2
            try:
                command.downgrade(config, "20260927_0049")
            except Exception:
                pass
            else:
                raise AssertionError("nonempty cancellation history downgrade accepted")
            with connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0] == "20260930_0050"
                assert db.execute("SELECT count(*) FROM plm.job_parse_cancel_versions").fetchone()[0] == 1
            print("PAR-01-A05-P01-P04-P03-P01 PASS: empty and populated up/down/up, ORM parity, "
                  "source/version constraints, immutable history, nonempty downgrade refused")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    run()
