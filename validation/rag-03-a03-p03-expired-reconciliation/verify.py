"""Windows 11/PostgreSQL 18 proof for expired RAG build reconciliation."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.rag.application.reconcile_expired_build import (
    ExpiredRAGEmbeddingBuildReconciler,
    RAGEmbeddingBuildReconciliationError,
)
from plm_assistant.modules.rag.infrastructure.expired_build_reconciliation_repository import (
    SqlAlchemyExpiredRAGEmbeddingBuildReconciliationRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/rag-03-a03-p02-build-begin/verify.py",
    "rag_expired_build_fixture",
)


class FixedSystemActor:
    def __init__(self, actor_id): self.actor_id = actor_id
    def assert_current(self): return self.actor_id


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit failure")


def reject(operation, expected: str) -> None:
    try:
        operation()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError(f"operation unexpectedly succeeded: {expected}")


def validate(context: dict[str, object]) -> None:
    database = context["database"]
    runtime = context["runtime"]
    planned = context["planned"]
    claim = context["claim"]
    actor = context["actor"]
    project = context["project"]
    config = context["config"]
    system_name = "synthetic-rag-reconciler-" + uuid.uuid4().hex[:12]
    with fixture.connect(database) as db:
        system_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (system_name, system_name),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.job_leases SET lease_expires_at=acquired_at "
            "+ interval '1 microsecond' WHERE job_id=%s AND fencing_token=%s",
            (claim.job_id, claim.fencing_token),
        )
        db.execute(
            "UPDATE plm.job_jobs job SET lease_expires_at=lease.lease_expires_at "
            "FROM plm.job_leases lease WHERE job.job_id=lease.job_id "
            "AND job.fencing_token=lease.fencing_token AND job.job_id=%s",
            (claim.job_id,),
        )

    generic_claim = JobLeaseService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyJobLeaseRepository(),
    ).claim_next(worker_ref="generic-must-not-split-rag", lease_seconds=60)
    assert generic_claim is None or generic_claim.job_id != claim.job_id
    assert context["claims"].claim_next(
        worker_ref="rag-must-defer-expiry", lease_seconds=60,
    ) is None
    with fixture.connect(database) as db:
        assert db.execute(
            "SELECT state FROM plm.job_jobs WHERE job_id=%s", (claim.job_id,),
        ).fetchone()[0] == "RUNNING"

    def reconciler(audit):
        return ExpiredRAGEmbeddingBuildReconciler(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyExpiredRAGEmbeddingBuildReconciliationRepository(),
            audit=audit,
            system_actor=FixedSystemActor(system_id),
        )

    try:
        reconciler(FailingAudit()).reconcile_next()
    except RAGEmbeddingBuildReconciliationError:
        pass
    else:
        raise AssertionError("Audit failure committed RAG reconciliation")
    with fixture.connect(database) as db:
        rolled_back = db.execute(
            "SELECT job.state,lease.state,attempt.completed_at,build.build_state,"
            "idx.index_state,array_agg(batch.batch_state ORDER BY batch.batch_ordinal) "
            "FROM plm.job_jobs job JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "AND lease.fencing_token=job.fencing_token JOIN plm.job_attempts attempt "
            "ON attempt.job_id=job.job_id AND attempt.fencing_token=job.fencing_token "
            "JOIN plm.rag_embedding_builds build ON build.build_job_ref=job.job_id "
            "JOIN plm.rag_embedding_indexes idx ON idx.embedding_index_id=build.embedding_index_id "
            "JOIN plm.rag_embedding_build_batches batch "
            "ON batch.embedding_build_id=build.embedding_build_id WHERE job.job_id=%s "
            "GROUP BY job.state,lease.state,attempt.completed_at,build.build_state,idx.index_state",
            (claim.job_id,),
        ).fetchone()
    assert rolled_back == (
        "RUNNING", "ACTIVE", None, "RUNNING", "BUILDING", ["PENDING", "PENDING"],
    )

    result = reconciler(AuditService(SqlAlchemyAuditRepository())).reconcile_next()
    assert result is not None
    assert result.job_id == claim.job_id
    assert result.embedding_build_id == planned.embedding_build_id
    assert result.embedding_index_id == planned.embedding_index_id
    assert result.prior_running_batch_count == 0
    assert result.error_code == "RAG_BUILD_LEASE_EXPIRED"
    assert not result.retryable
    assert reconciler(AuditService(SqlAlchemyAuditRepository())).reconcile_next() is None

    jobs = JobLeaseService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyJobLeaseRepository(),
    )
    try:
        jobs.heartbeat(
            job_id=claim.job_id, fencing_token=claim.fencing_token,
            worker_ref="rag-worker-01", lease_seconds=60,
        )
    except JobLeaseError:
        pass
    else:
        raise AssertionError("expired RAG worker renewed a reconciled lease")

    with fixture.connect(database) as db:
        terminal = db.execute(
            "SELECT job.state,job.completed_at,job.lease_expires_at,lease.state,"
            "attempt.error_code,attempt.completed_at,build.build_state,build.lock_version,"
            "idx.index_state,idx.lock_version,array_agg(batch.batch_state ORDER BY batch.batch_ordinal),"
            "array_agg(batch.error_code ORDER BY batch.batch_ordinal),"
            "bool_and(batch.started_at=batch.completed_at) "
            "FROM plm.job_jobs job JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "AND lease.fencing_token=job.fencing_token JOIN plm.job_attempts attempt "
            "ON attempt.job_id=job.job_id AND attempt.fencing_token=job.fencing_token "
            "JOIN plm.rag_embedding_builds build ON build.build_job_ref=job.job_id "
            "JOIN plm.rag_embedding_indexes idx ON idx.embedding_index_id=build.embedding_index_id "
            "JOIN plm.rag_embedding_build_batches batch ON batch.embedding_build_id=build.embedding_build_id "
            "WHERE job.job_id=%s GROUP BY job.state,job.completed_at,job.lease_expires_at,"
            "lease.state,attempt.error_code,attempt.completed_at,build.build_state,"
            "build.lock_version,idx.index_state,idx.lock_version",
            (claim.job_id,),
        ).fetchone()
        event = db.execute(
            "SELECT event_scope,target_project_id,actor_type,actor_id,original_actor_id,"
            "action,outcome,target_object_id,target_version_id,reason_code,before_state,after_state "
            "FROM plm.aud_events WHERE action='RAG_INDEX_BUILD_RECONCILED' AND trace_id=%s",
            (claim.trace_id,),
        ).fetchone()
    assert terminal[0] == "FAILED" and terminal[2] is None
    assert terminal[1] == terminal[5]
    assert terminal[3:10] == (
        "EXPIRED", "RAG_BUILD_LEASE_EXPIRED", terminal[1],
        "FAILED", 2, "FAILED", 2,
    )
    assert terminal[10:] == (
        ["CANCELLED", "CANCELLED"],
        ["RAG_BUILD_LEASE_EXPIRED", "RAG_BUILD_LEASE_EXPIRED"], True,
    )
    assert event == (
        "PROJECT", project, "SYSTEM", system_id, actor,
        "RAG_INDEX_BUILD_RECONCILED", "FAILED", planned.embedding_index_id,
        planned.embedding_build_id, "RAG_BUILD_LEASE_EXPIRED", "RUNNING", "FAILED",
    )
    reject(lambda: command.downgrade(config, "20261004_0080"),
           "reconciled RAG EmbeddingBuild history prevents downgrade")
    print(
        "RAG_03_A03_P03_EXPIRED_RECONCILIATION_PASS: Windows 11/PostgreSQL18.6 "
        "rolled back Job/Lease/Attempt/Build/Index/Batch changes on Audit failure, "
        "then atomically expired the single-attempt Job, failed Build/Index, cancelled "
        "two unsent batches, wrote one SYSTEM Audit, rejected stale Worker renewal and "
        "retained reconciled history; zero Provider I/O"
    )


def main() -> None:
    fixture.main(after_begin=validate)


if __name__ == "__main__":
    main()
