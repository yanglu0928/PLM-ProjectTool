"""Windows 11/PostgreSQL 18 proof for the RAG batch pre-network fence."""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import replace
from pathlib import Path

from alembic import command

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.rag.application.embedding_batch_send_fence import (
    RAGEmbeddingBatchPayloadProof,
    RAGEmbeddingBatchSendFenceError,
    RAGEmbeddingBatchSendFenceService,
)
from plm_assistant.modules.rag.application.reconcile_expired_build import (
    ExpiredRAGEmbeddingBuildReconciler,
)
from plm_assistant.modules.rag.infrastructure.embedding_batch_send_fence_repository import (
    SqlAlchemyRAGEmbeddingBatchSendFenceRepository,
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
    "rag_batch_send_fence_fixture",
)
reconciliation_fixture = load(
    ROOT / "validation/rag-03-a03-p03-expired-reconciliation/verify.py",
    "rag_batch_send_fence_reconciliation_fixture",
)


def validate(context: dict[str, object]) -> None:
    database = context["database"]
    runtime = context["runtime"]
    planned = context["planned"]
    claim = context["claim"]
    batches = context["batches"]
    actor = context["actor"]
    config = context["config"]
    first = batches[0]
    proof = RAGEmbeddingBatchPayloadProof(
        planned.embedding_build_id, planned.embedding_index_id,
        first.batch_ordinal, first.source_first_ordinal,
        first.source_record_count, first.source_batch_fingerprint,
        first.payload_fingerprint, first.payload_bytes, first.input_tokens,
    )
    service = RAGEmbeddingBatchSendFenceService(
        unit_of_work=runtime.unit_of_work,
        claims=context["claims"],
        repository=SqlAlchemyRAGEmbeddingBatchSendFenceRepository(),
    )
    try:
        service.fence(
            proof=replace(proof, payload_fingerprint=b"x" * 32),
            job_id=claim.job_id, fencing_token=claim.fencing_token,
            worker_ref="rag-worker-01",
        )
    except RAGEmbeddingBatchSendFenceError:
        pass
    else:
        raise AssertionError("mismatched payload crossed the send fence")
    with fixture.connect(database) as db:
        assert db.execute(
            "SELECT batch_state,send_fencing_token,started_at,lock_version "
            "FROM plm.rag_embedding_build_batches WHERE embedding_build_id=%s "
            "AND batch_ordinal=1", (planned.embedding_build_id,),
        ).fetchone() == ("PENDING", None, None, 0)

    fenced = service.fence(
        proof=proof, job_id=claim.job_id, fencing_token=claim.fencing_token,
        worker_ref="rag-worker-01",
    )
    assert fenced.material.lock_version == 1
    assert fenced.material.egress_authorization_ref == first.egress_authorization_ref
    assert fenced.material.ai_model_id.int
    with fixture.connect(database) as db:
        state = db.execute(
            "SELECT batch_state,send_fencing_token,provider_request_ref,error_code,"
            "started_at,completed_at,lock_version FROM plm.rag_embedding_build_batches "
            "WHERE embedding_build_id=%s ORDER BY batch_ordinal",
            (planned.embedding_build_id,),
        ).fetchall()
        assert state[0][0:4] == ("RUNNING", 1, None, None)
        assert state[0][4] is not None and state[0][5] is None and state[0][6] == 1
        assert state[1] == ("PENDING", None, None, None, None, None, 0)
        system_name = "synthetic-rag-fence-reconciler-" + uuid.uuid4().hex[:10]
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

    reconciler = ExpiredRAGEmbeddingBuildReconciler(
        unit_of_work=runtime.unit_of_work,
        store=SqlAlchemyExpiredRAGEmbeddingBuildReconciliationRepository(),
        audit=AuditService(SqlAlchemyAuditRepository()),
        system_actor=reconciliation_fixture.FixedSystemActor(system_id),
    )
    terminal = reconciler.reconcile_next()
    assert terminal is not None
    assert terminal.prior_running_batch_count == 1
    assert terminal.error_code == "RAG_PROVIDER_OUTCOME_UNKNOWN"
    with fixture.connect(database) as db:
        states = db.execute(
            "SELECT batch_state,error_code,send_fencing_token,started_at,completed_at "
            "FROM plm.rag_embedding_build_batches WHERE embedding_build_id=%s "
            "ORDER BY batch_ordinal", (planned.embedding_build_id,),
        ).fetchall()
    assert states[0][0:3] == ("UNKNOWN", "RAG_PROVIDER_OUTCOME_UNKNOWN", 1)
    assert states[0][3] < states[0][4]
    assert states[1][0:3] == ("CANCELLED", "RAG_BUILD_LEASE_EXPIRED", None)
    assert states[1][3] == states[1][4]
    try:
        command.downgrade(config, "20261004_0081")
    except Exception as error:
        assert "fenced RAG EmbeddingBuildBatch history prevents downgrade" in str(error)
    else:
        raise AssertionError("fenced batch history was downgraded")
    print(
        "RAG_03_A04_P01_BATCH_SEND_FENCE_PASS: Windows 11/PostgreSQL18.6 "
        "rejected a mismatched payload, atomically persisted one exact authorized "
        "PENDING-to-RUNNING batch before any Provider I/O, preserved one unsent "
        "batch, converted the expired in-flight batch to UNKNOWN without replay, "
        "and refused downgrade across fenced history; zero Provider I/O"
    )


def main() -> None:
    fixture.main(after_begin=validate)


if __name__ == "__main__":
    main()
