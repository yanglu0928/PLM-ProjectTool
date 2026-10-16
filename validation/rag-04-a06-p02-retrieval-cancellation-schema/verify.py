"""Windows 11/PostgreSQL 18 proof for Schema0090 Retrieval cancellation."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema_fixture = load(
    ROOT / "validation/rag-04-a02-p01-retrieval-schema/verify.py",
    "rag_cancel_schema_fixture",
)
create_fixture = load(
    ROOT / "validation/rag-04-a02-p02-retrieval-create/verify.py",
    "rag_cancel_create_fixture",
)
terminal_fixture = load(
    ROOT / "validation/rag-04-a05-p01-retrieval-terminal-schema/verify.py",
    "rag_cancel_terminal_fixture",
)
begin_fixture = create_fixture.begin_fixture


def reject(db, operation, expected: str) -> None:
    try:
        with db.transaction():
            operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"database operation unexpectedly succeeded: {expected}")


def verify_migration_cycle() -> None:
    database = schema_fixture.create_database("rag04a06p02mig_")
    try:
        cfg = schema_fixture.config(database)
        command.upgrade(cfg, "20261004_0089")
        actor = uuid.uuid4()
        with schema_fixture.connect(database) as db:
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized,state,deployment_role) "
                "VALUES (%s,'0090 existing actor','0090-existing-actor',"
                "'DISABLED','NONE')", (actor,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with schema_fixture.connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (actor,),
            ).fetchone()[0] == 1
            constraint = db.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE connamespace='plm'::regnamespace AND "
                "conname='ck_rag_retrieval_runs__lifecycle'"
            ).fetchone()
            assert constraint is not None and "CANCELLED" in constraint[0]
        command.downgrade(cfg, "20261004_0089")
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        schema_fixture.drop_database(database)


def _cancel_pending(db, *, run_id, job_id, actor) -> None:
    requested_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
    db.execute(
        "UPDATE plm.job_jobs SET state='CANCEL_REQUESTED',"
        "cancel_requested_by=%s,cancel_requested_at=%s,cancel_reason='fixture' "
        "WHERE job_id=%s", (actor, requested_at, job_id),
    )
    completed_at = db.execute("SELECT clock_timestamp()").fetchone()[0]
    db.execute(
        "UPDATE plm.job_jobs SET state='CANCELLED',completed_at=%s "
        "WHERE job_id=%s", (completed_at, job_id),
    )
    db.execute(
        "UPDATE plm.rag_retrieval_runs SET retrieval_state='CANCELLED',"
        "rerank_state='NOT_APPLICABLE',egress_state='NOT_APPLICABLE',"
        "quality_flags='[]'::jsonb,error_code=NULL,completed_at=%s,"
        "lock_version=1 WHERE retrieval_run_id=%s", (completed_at, run_id),
    )


def _cancel_claimed(db, *, claim, actor) -> None:
    requested_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
    db.execute(
        "UPDATE plm.job_jobs SET state='CANCEL_REQUESTED',"
        "cancel_requested_by=%s,cancel_requested_at=%s,cancel_reason='fixture' "
        "WHERE job_id=%s", (actor, requested_at, claim.job_id),
    )
    completed_at = db.execute("SELECT clock_timestamp()").fetchone()[0]
    db.execute(
        "UPDATE plm.job_leases SET state='RELEASED' "
        "WHERE job_id=%s AND fencing_token=1", (claim.job_id,),
    )
    db.execute(
        "UPDATE plm.job_attempts SET completed_at=%s,error_code='JOB_CANCELLED' "
        "WHERE job_id=%s AND fencing_token=1", (completed_at, claim.job_id),
    )
    db.execute(
        "UPDATE plm.job_jobs SET state='CANCELLED',lease_expires_at=NULL,"
        "completed_at=%s WHERE job_id=%s", (completed_at, claim.job_id),
    )
    db.execute(
        "UPDATE plm.rag_retrieval_runs SET retrieval_state='CANCELLED',"
        "rerank_state='NOT_APPLICABLE',egress_state='NOT_APPLICABLE',"
        "quality_flags='[]'::jsonb,error_code=NULL,completed_at=%s,"
        "lock_version=1 WHERE retrieval_run_id=%s",
        (completed_at, claim.retrieval_run_id),
    )


def verify_cancel_paths(context, envelope, sender, adapter) -> None:
    create_fixture.execute(
        context, envelope, sender, adapter, query_text="PLM cancellation",
    )
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
        direct = db.execute(
            "SELECT retrieval_run_id,job_id FROM plm.rag_retrieval_runs "
            "WHERE project_id=%s ORDER BY created_at LIMIT 1", (project,),
        ).fetchone()
        with db.transaction():
            _cancel_pending(db, run_id=direct[0], job_id=direct[1], actor=actor)
        assert db.execute(
            "SELECT run.retrieval_state,run.lock_version,job.state,"
            "job.lock_version,job.attempt_count,job.fencing_token,"
            "(SELECT count(*) FROM plm.job_leases WHERE job_id=job.job_id),"
            "(SELECT count(*) FROM plm.job_attempts WHERE job_id=job.job_id) "
            "FROM plm.rag_retrieval_runs run JOIN plm.job_jobs job "
            "ON job.job_id=run.job_id WHERE run.retrieval_run_id=%s", (direct[0],),
        ).fetchone() == ("CANCELLED", 1, "CANCELLED", 2, 0, 0, 0, 0)

    claimed_run, claimed_job = terminal_fixture.create_pending_run(
        database, actor=actor, project=project, index_id=index_id,
    )
    claimed = terminal_fixture.claim(runtime, lease_seconds=60)
    assert (claimed.retrieval_run_id, claimed.job_id) == (claimed_run, claimed_job)
    with begin_fixture.connect(database) as db:
        with db.transaction():
            _cancel_claimed(db, claim=claimed, actor=actor)
        assert db.execute(
            "SELECT run.retrieval_state,job.state,job.lock_version,lease.state,"
            "attempt.error_code FROM plm.rag_retrieval_runs run "
            "JOIN plm.job_jobs job ON job.job_id=run.job_id "
            "JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id "
            "WHERE run.retrieval_run_id=%s", (claimed_run,),
        ).fetchone() == ("CANCELLED", "CANCELLED", 3, "RELEASED", "JOB_CANCELLED")

    partial_run, partial_job = terminal_fixture.create_pending_run(
        database, actor=actor, project=project, index_id=index_id,
    )
    with begin_fixture.connect(database) as db:
        def job_only():
            requested_at = db.execute("SELECT statement_timestamp()").fetchone()[0]
            db.execute(
                "UPDATE plm.job_jobs SET state='CANCEL_REQUESTED',"
                "cancel_requested_by=%s,cancel_requested_at=%s,"
                "cancel_reason='fixture' WHERE job_id=%s",
                (actor, requested_at, partial_job),
            )
            db.execute(
                "UPDATE plm.job_jobs SET state='CANCELLED',"
                "completed_at=clock_timestamp() WHERE job_id=%s", (partial_job,),
            )
        reject(db, job_only, "terminal transaction is incomplete")
        assert db.execute(
            "SELECT run.retrieval_state,job.state FROM plm.rag_retrieval_runs run "
            "JOIN plm.job_jobs job ON job.job_id=run.job_id "
            "WHERE run.retrieval_run_id=%s", (partial_run,),
        ).fetchone() == ("RUNNING", "PENDING")

        def cancel_with_result():
            terminal_fixture.candidate_insert(
                db, run_id=partial_run, project=project, index_id=index_id,
            )
            _cancel_pending(
                db, run_id=partial_run, job_id=partial_job, actor=actor,
            )
        reject(db, cancel_with_result, "cancelled terminal transaction is invalid")

    try:
        command.downgrade(schema_fixture.config(database), "20261004_0089")
    except Exception as error:
        assert "cancelled RAG Retrieval history prevents downgrade" in str(error)
    else:
        raise AssertionError("Schema0090 downgrade accepted cancellation history")


def main() -> None:
    verify_migration_cycle()
    create_fixture.activation_fixture.send_fixture.main(
        execute=verify_cancel_paths, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )
    print(
        "RAG_04_A06_P02_RETRIEVAL_CANCELLATION_SCHEMA_PASS: Schema0090 "
        "migration, drift, pending/claimed atomic cancellation, partial rollback "
        "and retained-history downgrade refusal passed on Windows 11/PostgreSQL 18.6"
    )


if __name__ == "__main__":
    main()
