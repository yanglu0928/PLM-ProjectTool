"""Windows 11/PostgreSQL 18 proof for Retrieval owner-only claim routing."""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaims
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


create_fixture = load(
    ROOT / "validation/rag-04-a02-p02-retrieval-create/verify.py",
    "rag_retrieval_claim_create_fixture",
)
begin_fixture = create_fixture.begin_fixture


def execute(context, envelope, sender, adapter, *, after_claim=None,
            retrieval_query=None) -> None:
    create_fixture.execute(
        context, envelope, sender, adapter, query_text=retrieval_query,
    )
    database, runtime = context["database"], context["runtime"]
    with begin_fixture.connect(database) as db:
        job_id, run_id, project_id, actor_id = db.execute(
            "SELECT job.job_id,run.retrieval_run_id,run.project_id,run.actor_ref "
            "FROM plm.job_jobs job JOIN plm.rag_retrieval_runs run "
            "ON run.job_id=job.job_id WHERE job.owner_module='rag' "
            "AND job.job_type='RAG_RETRIEVAL' ORDER BY job.created_at DESC LIMIT 1"
        ).fetchone()

    generic = JobLeaseService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyJobLeaseRepository(),
    )
    assert generic.claim_next(
        worker_ref="generic-must-not-steal-retrieval", lease_seconds=30,
    ) is None
    assert generic.claim_next_parse(
        worker_ref="parser-must-not-steal-retrieval", lease_seconds=30,
    ) is None
    assert generic.claim_next_ai_task(
        worker_ref="ai-must-not-steal-retrieval", lease_seconds=30,
    ) is None
    assert generic.claim_next_rag_build(
        worker_ref="build-must-not-steal-retrieval", lease_seconds=30,
    ) is None

    claims = RAGRetrievalClaims(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyRAGRetrievalClaimRepository(),
    )
    claim = claims.claim_next(worker_ref="rag-retrieval-01", lease_seconds=3)
    assert claim is not None
    assert (claim.job_id, claim.retrieval_run_id, claim.project_id, claim.actor_id) == (
        job_id, run_id, project_id, actor_id,
    )
    assert claim.fencing_token == 1 and claim.attempt_no == 1
    with runtime.unit_of_work() as tx:
        current = claims.check_current(
            tx, job_id=claim.job_id, fencing_token=1,
            worker_ref="rag-retrieval-01",
        )
        assert (
            current.job_id, current.retrieval_run_id, current.project_id,
            current.actor_id, current.trace_id, current.fencing_token,
            current.attempt_no, current.lease_expires_at,
        ) == (
            claim.job_id, claim.retrieval_run_id, claim.project_id,
            claim.actor_id, claim.trace_id, claim.fencing_token,
            claim.attempt_no, claim.lease_expires_at,
        )
        assert current.observed_at >= claim.observed_at
        tx.commit()

    assert claims.claim_next(
        worker_ref="rag-retrieval-02", lease_seconds=30,
    ) is None
    if after_claim is not None:
        after_claim({
            **context, "job_id": job_id, "retrieval_run_id": run_id,
            "claim": claim, "claims": claims,
        })
    time.sleep(4)
    assert generic.claim_next(
        worker_ref="generic-after-expiry", lease_seconds=30,
    ) is None
    assert claims.claim_next(
        worker_ref="retrieval-after-expiry", lease_seconds=30,
    ) is None

    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT state,attempt_count,max_attempts,fencing_token,completed_at IS NULL "
            "FROM plm.job_jobs WHERE job_id=%s", (job_id,),
        ).fetchone() == ("RUNNING", 1, 1, 1, True)
        assert db.execute(
            "SELECT state,worker_ref,fencing_token FROM plm.job_leases "
            "WHERE job_id=%s", (job_id,),
        ).fetchone() == ("ACTIVE", "rag-retrieval-01", 1)
        assert db.execute(
            "SELECT retrieval_state,lock_version FROM plm.rag_retrieval_runs "
            "WHERE retrieval_run_id=%s", (run_id,),
        ).fetchone() == ("RUNNING", 0)

    print(
        "RAG_04_A03_P02_RETRIEVAL_CLAIM_PASS: generic, parser, AI and RAG-build "
        "workers could not claim Retrieval; the owner claim returned the exact single "
        "generation; expired Retrieval remained untouched for atomic reconciliation"
    )


def main(*, after_claim=None, retrieval_query=None) -> None:
    def validate(context, envelope, sender, adapter):
        execute(
            context, envelope, sender, adapter, after_claim=after_claim,
            retrieval_query=retrieval_query,
        )

    create_fixture.activation_fixture.send_fixture.main(
        execute=validate, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
