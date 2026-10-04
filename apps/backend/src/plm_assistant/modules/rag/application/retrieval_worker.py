"""One-shot FTS Retrieval Worker with no external provider I/O."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaim,
    RAGRetrievalClaims,
)

from .fts_retrieval_merge import FTSRetrievalMergePlanner
from .prepare_retrieval_query import (
    PreparedRAGRetrieval,
    RAGRetrievalPreparationError,
    RAGRetrievalQueryPreparationService,
)
from .project_fts_candidates import ProjectFTSCandidatePlanner
from .retrieval_terminal import (
    PublishedRAGRetrievalTerminal,
    RAGRetrievalTerminalError,
    RAGRetrievalTerminalService,
)


class RAGRetrievalWorkerError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_WORKER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGRetrievalWorkerCycle:
    state: str
    job_id: uuid.UUID | None = None
    retrieval_run_id: uuid.UUID | None = None
    context_bundle_id: uuid.UUID | None = None
    candidate_count: int = 0
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.state == "IDLE":
            if (self.job_id is not None or self.retrieval_run_id is not None
                    or self.context_bundle_id is not None
                    or self.candidate_count != 0 or self.error_code is not None):
                raise RAGRetrievalWorkerError()
            return
        if (type(self.job_id) is not uuid.UUID or not self.job_id.int
                or type(self.retrieval_run_id) is not uuid.UUID
                or not self.retrieval_run_id.int
                or type(self.candidate_count) is not int
                or not 0 <= self.candidate_count <= 100):
            raise RAGRetrievalWorkerError()
        if self.state == "SUCCEEDED":
            if (type(self.context_bundle_id) is not uuid.UUID
                    or not self.context_bundle_id.int
                    or self.candidate_count < 1 or self.error_code is not None):
                raise RAGRetrievalWorkerError()
            return
        if self.state in {"FAILED", "RECONCILIATION_PENDING"}:
            if (self.context_bundle_id is not None or self.candidate_count != 0
                    or type(self.error_code) is not str
                    or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None):
                raise RAGRetrievalWorkerError()
            return
        raise RAGRetrievalWorkerError()


class RAGRetrievalOneShotWorker:
    """Claim, decrypt, search, merge and atomically publish one Retrieval."""

    LEASE_SECONDS = 300

    def __init__(self, *, claims: RAGRetrievalClaims,
                 preparation: RAGRetrievalQueryPreparationService,
                 candidates: ProjectFTSCandidatePlanner,
                 merge: FTSRetrievalMergePlanner,
                 terminal: RAGRetrievalTerminalService) -> None:
        if any(value is None for value in (
                claims, preparation, candidates, merge, terminal)):
            raise ValueError("RAG Retrieval Worker dependencies required")
        self._claims = claims
        self._preparation = preparation
        self._candidates = candidates
        self._merge = merge
        self._terminal = terminal

    def run_once(self, *, worker_ref: str) -> RAGRetrievalWorkerCycle:
        try:
            JobLeaseService._validate_worker(worker_ref)
            claim = self._claims.claim_next(
                worker_ref=worker_ref, lease_seconds=self.LEASE_SECONDS,
            )
        except JobLeaseError:
            raise RAGRetrievalWorkerError("JOB_STORE_UNAVAILABLE") from None
        except Exception:
            raise RAGRetrievalWorkerError("JOB_STORE_UNAVAILABLE") from None
        if claim is None:
            return RAGRetrievalWorkerCycle("IDLE")
        self._require_claim(claim)
        try:
            published = self._preparation.consume_current_query(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref=worker_ref,
                consumer=lambda transaction, prepared: self._complete(
                    transaction, claim, worker_ref, prepared,
                ),
            )
            if type(published) is not PublishedRAGRetrievalTerminal:
                raise RAGRetrievalTerminalError()
            published.__post_init__()
            return RAGRetrievalWorkerCycle(
                "SUCCEEDED", claim.job_id, claim.retrieval_run_id,
                published.context_bundle_id, published.candidate_count,
            )
        except RAGRetrievalPreparationError as error:
            code = ("RAG_NO_AUTHORIZED_CANDIDATES"
                    if error.code == "RAG_NO_AUTHORIZED_CANDIDATES"
                    else "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE")
            return self._fail(claim, worker_ref, code)
        except RAGRetrievalTerminalError as error:
            return RAGRetrievalWorkerCycle(
                "RECONCILIATION_PENDING", claim.job_id,
                claim.retrieval_run_id, error_code=error.code,
            )
        except Exception:
            return self._fail(
                claim, worker_ref, "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE",
            )

    def _complete(self, transaction: object, claim: RAGRetrievalClaim,
                  worker_ref: str, prepared: PreparedRAGRetrieval
                  ) -> PublishedRAGRetrievalTerminal:
        candidates = self._candidates.plan(transaction, prepared=prepared)
        plan = self._merge.plan(candidates, top_k=prepared.top_k)
        return self._terminal.publish_success_in_transaction(
            transaction, job_id=claim.job_id,
            fencing_token=claim.fencing_token, worker_ref=worker_ref,
            prepared=prepared, plan=plan,
        )

    def _fail(self, claim: RAGRetrievalClaim, worker_ref: str,
              error_code: str) -> RAGRetrievalWorkerCycle:
        try:
            result = self._terminal.publish_failure(
                job_id=claim.job_id, fencing_token=claim.fencing_token,
                worker_ref=worker_ref, error_code=error_code,
            )
            if type(result) is not PublishedRAGRetrievalTerminal:
                raise RAGRetrievalTerminalError()
            result.__post_init__()
            return RAGRetrievalWorkerCycle(
                "FAILED", claim.job_id, claim.retrieval_run_id,
                error_code=result.error_code,
            )
        except RAGRetrievalTerminalError as error:
            return RAGRetrievalWorkerCycle(
                "RECONCILIATION_PENDING", claim.job_id,
                claim.retrieval_run_id, error_code=error.code,
            )
        except Exception:
            return RAGRetrievalWorkerCycle(
                "RECONCILIATION_PENDING", claim.job_id,
                claim.retrieval_run_id,
                error_code="RAG_RETRIEVAL_TERMINAL_UNAVAILABLE",
            )

    @staticmethod
    def _require_claim(claim: RAGRetrievalClaim) -> None:
        if type(claim) is not RAGRetrievalClaim:
            raise RAGRetrievalWorkerError("JOB_STORE_UNAVAILABLE")
        try:
            claim.__post_init__()
        except Exception:
            raise RAGRetrievalWorkerError("JOB_STORE_UNAVAILABLE") from None
