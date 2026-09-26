"""Reproduce current DEPLOYMENT Job/Outbox schema gap in an owned database."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from alembic import command
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

spec=spec_from_file_location("_audit_export_schema_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def main():
    name="auditexportcheck_"+uuid4().hex[:12]
    with fixture.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"20260926_0035")
            with fixture.schema.connect(name) as db:
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]=="20260926_0035"
                for table,constraint,statement,args in (
                    ("job_jobs","ck_job_jobs__scope","INSERT INTO plm.job_jobs(owner_module,job_type,scope,payload_refs,idempotency_key,max_attempts,trace_id) VALUES ('audit','AUDIT_EXPORT','DEPLOYMENT','{}',%s,3,%s)",(str(uuid4()),str(uuid4()))),
                    ("job_outbox_events","ck_job_outbox_events__scope","INSERT INTO plm.job_outbox_events(event_type,owner_module,scope,aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id) VALUES ('AUDIT_EXPORT_REQUESTED','audit','DEPLOYMENT',%s,1,'{}',%s,%s)",(uuid4(),str(uuid4()),str(uuid4()))),
                ):
                    try:
                        with db.transaction():db.execute(statement,args)
                    except psycopg.errors.CheckViolation as exc:
                        assert exc.diag.constraint_name==constraint
                    else:raise AssertionError("expected current DEPLOYMENT schema gap not reproduced")
                    assert db.execute(sql.SQL("SELECT count(*) FROM plm.{}").format(sql.Identifier(table))).fetchone()[0]==0
            print("AUD-03-A01 evidence PASS: head0035 DEPLOYMENT Job/Outbox inserts rejected by scope checks, no persisted rows; export implementation NOT PASS, prerequisite migration required")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
