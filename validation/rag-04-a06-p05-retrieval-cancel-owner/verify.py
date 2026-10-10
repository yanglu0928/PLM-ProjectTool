"""Windows 11/PostgreSQL 18 proof for Retrieval cancellation Owners."""

from __future__ import annotations

import importlib.util
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.jobs.application.cancel_request import (
    ProjectJobCancellation,
    RequestProjectJobCancel,
)
from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaims
from plm_assistant.modules.jobs.infrastructure.rag_retrieval_claim_repository import (
    SqlAlchemyRAGRetrievalClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.rag.api.retrieval_cancel import create_rag_retrieval_cancel_router
from plm_assistant.modules.rag.application.retrieval_cancel import (
    RAGRetrievalCancelOwner,
    RAGRetrievalCancelReconciler,
)
from plm_assistant.modules.rag.infrastructure.retrieval_cancel_repository import (
    SqlAlchemyRAGRetrievalCancellationRepository,
)
from plm_assistant.modules.rag.infrastructure.retrieval_query_crypto import (
    AesGcmRetrievalQueryCrypto,
)


ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://plm.example.test"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker_fixture = load(
    ROOT / "validation/rag-04-a05-p02-retrieval-worker-context/verify.py",
    "rag_cancel_worker_fixture",
)
create_fixture = worker_fixture.create_fixture
begin_fixture = worker_fixture.begin_fixture


class IssueAccess:
    def can_issue(self, *_args, **_kwargs): return False


def execute(context, envelope, sender, adapter) -> None:
    create_fixture.execute(
        context, envelope, sender, adapter,
        query_text="PLM cancel owner pending",
    )
    database, runtime = context["database"], context["runtime"]
    actor, project = context["actor"], context["project"]
    index_id = context["planned"].embedding_index_id
    token, csrf = b"z" * 32, create_fixture.CSRF
    with begin_fixture.connect(database) as db:
        db.execute(
            "UPDATE plm.prj_project_members SET state='ACTIVE' "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        )
        direct = db.execute(
            "SELECT retrieval_run_id,job_id FROM plm.rag_retrieval_runs "
            "WHERE project_id=%s AND retrieval_state='RUNNING' "
            "ORDER BY created_at LIMIT 1", (project,),
        ).fetchone()
    guard = create_fixture.activation_fixture.quality_fixture.Guard()
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository(),
    )
    audit = AuditService(SqlAlchemyAuditRepository())
    receipts = SqlAlchemyIdempotencyReceipts()
    repository = SqlAlchemyRAGRetrievalCancellationRepository()
    owner = RAGRetrievalCancelOwner(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(), authorization=authorization,
        license_guard=guard, repository=repository, receipts=receipts,
        audit=audit, clock=lambda: datetime.now(timezone.utc),
    )
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=IssueAccess(),
        audit=audit, idempotency=receipts,
    )
    router = create_rag_retrieval_cancel_router(
        sessions=sessions, cancellations=owner,
        origins=LoginOriginPolicy([ORIGIN]),
    )
    headers = {
        "origin": ORIGIN, "host": "plm.example.test",
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": csrf.hex(),
        "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
    }
    path = (
        f"/api/v1/projects/{project}/retrieval-runs/{direct[0]}:cancel"
    )
    with TestClient(
        create_app(rag_retrieval_cancel_router=router), base_url=ORIGIN,
    ) as client:
        response = client.post(
            path, json={"reason": "synthetic direct cancellation"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["state"] == "CANCELLED"
        assert response.headers["etag"] == '"v1"'
        assert client.post(
            path, json={"reason": "synthetic direct cancellation"},
            headers=headers,
        ).json()["data"] == response.json()["data"]
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT run.retrieval_state,run.lock_version,job.state,"
            "job.lock_version,job.attempt_count,"
            "(SELECT count(*) FROM plm.aud_events WHERE "
            "target_object_id=run.retrieval_run_id AND "
            "action='RAG_RETRIEVAL_CANCELLED') "
            "FROM plm.rag_retrieval_runs run JOIN plm.job_jobs job "
            "ON job.job_id=run.job_id WHERE run.retrieval_run_id=%s",
            (direct[0],),
        ).fetchone() == ("CANCELLED", 1, "CANCELLED", 2, 0, 1)

    keys = create_fixture.Keys()
    cipher = AesGcmRetrievalQueryCrypto(keys, key_ref="rag-query-proof.v1")
    run_id, job_id = worker_fixture.create_pending(
        database, actor=actor, project=project, index_id=index_id,
        query="PLM cooperative cancel", cipher=cipher,
    )
    claims = RAGRetrievalClaims(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyRAGRetrievalClaimRepository(),
    )
    claim = claims.claim_next(worker_ref="rag-cancel-proof", lease_seconds=60)
    assert claim is not None and (claim.retrieval_run_id, claim.job_id) == (
        run_id, job_id,
    )
    dispatcher = ProjectJobCancellation(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyJobReadRepository(), sessions=sessions,
        license_guard=guard,
        owners={("rag", "RAG_RETRIEVAL"): owner},
    )
    job_key = str(uuid.uuid4())
    job_command = RequestProjectJobCancel(
        job_id, project, token, csrf, uuid.uuid4(),
        "synthetic cooperative cancellation", 1,
    )
    requested = dispatcher.cancel(job_command, idempotency_key=job_key)
    assert (requested.state, requested.lock_version) == (
        "CANCEL_REQUESTED", 2,
    )
    reconciler = RAGRetrievalCancelReconciler(
        unit_of_work=runtime.unit_of_work, repository=repository, audit=audit,
        system_actor=worker_fixture.FixedSystemActor(actor),
    )
    completed = reconciler.reconcile_current(
        job_id=job_id, fencing_token=1, worker_ref="rag-cancel-proof",
    )
    assert completed.lease_outcome == "RELEASED"
    replay = dispatcher.cancel(job_command, idempotency_key=job_key)
    assert replay == requested
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT run.retrieval_state,job.state,job.lock_version,lease.state,"
            "attempt.error_code FROM plm.rag_retrieval_runs run "
            "JOIN plm.job_jobs job ON job.job_id=run.job_id "
            "JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id "
            "WHERE run.retrieval_run_id=%s", (run_id,),
        ).fetchone() == (
            "CANCELLED", "CANCELLED", 3, "RELEASED", "JOB_CANCELLED",
        )

    expired_run, expired_job = worker_fixture.create_pending(
        database, actor=actor, project=project, index_id=index_id,
        query="PLM expired cancel", cipher=cipher,
    )
    expired_claim = claims.claim_next(
        worker_ref="rag-expired-proof", lease_seconds=3,
    )
    assert expired_claim is not None and expired_claim.job_id == expired_job
    expired_command = RequestProjectJobCancel(
        expired_job, project, token, csrf, uuid.uuid4(),
        "synthetic expired cancellation", 1,
    )
    assert dispatcher.cancel(
        expired_command, idempotency_key=str(uuid.uuid4()),
    ).state == "CANCEL_REQUESTED"
    time.sleep(3.2)
    expired = reconciler.reconcile_expired_next()
    assert expired is not None and (
        expired.retrieval_run_id, expired.lease_outcome,
    ) == (expired_run, "EXPIRED")
    with begin_fixture.connect(database) as db:
        assert db.execute(
            "SELECT run.retrieval_state,job.state,job.lock_version,lease.state,"
            "attempt.error_code FROM plm.rag_retrieval_runs run "
            "JOIN plm.job_jobs job ON job.job_id=run.job_id "
            "JOIN plm.job_leases lease ON lease.job_id=job.job_id "
            "JOIN plm.job_attempts attempt ON attempt.job_id=job.job_id "
            "WHERE run.retrieval_run_id=%s", (expired_run,),
        ).fetchone() == (
            "CANCELLED", "CANCELLED", 3, "EXPIRED", "JOB_CANCELLED",
        )
        assert db.execute(
            "SELECT count(*) FROM plm.rag_retrieval_candidates "
            "WHERE retrieval_run_id IN (%s,%s,%s)",
            (direct[0], run_id, expired_run),
        ).fetchone()[0] == 0
    print(
        "RAG_04_A06_P05_RETRIEVAL_CANCEL_OWNER_PASS: alias HTTP direct "
        "cancel, generic Job registry cooperative cancel, exact replay, current "
        "worker and expired reconciliation passed atomically on Windows 11/"
        "PostgreSQL 18.6"
    )


def main() -> None:
    create_fixture.activation_fixture.send_fixture.main(
        execute=execute, source_bodies=("PLM begin one",),
        adapter_vector_value=0.01,
    )


if __name__ == "__main__":
    main()
