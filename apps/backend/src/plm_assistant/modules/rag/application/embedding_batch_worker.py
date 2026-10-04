"""Execute one exact RAG Embedding batch without automatic replay."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.application.embedding_execution_contract import (
    AIEmbeddingEnvelope,
)
from plm_assistant.modules.ai.application.embedding_response_contract import (
    AIEmbeddingResponseError,
    parse_embedding_response,
)
from plm_assistant.modules.ai.application.send_embedding_request import (
    AIEmbeddingSendError,
    SentAIEmbeddingResponse,
)

from .embedding_batch_failure import (
    PublishedRAGEmbeddingBatchFailure,
    RAGEmbeddingBatchFailureError,
    RAGEmbeddingBatchFailurePhase,
)
from .embedding_batch_success import (
    PublishedRAGEmbeddingBatch,
    RAGEmbeddingBatchSuccessError,
)


class RAGEmbeddingBatchWorkerError(RuntimeError):
    def __init__(self, code: str = "RAG_EMBEDDING_BATCH_WORKER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingBatchWorkerCycle:
    state: str
    job_id: uuid.UUID
    embedding_build_batch_id: uuid.UUID
    embedding_record_ids: tuple[uuid.UUID, ...] = ()
    error_code: str | None = None

    def __post_init__(self) -> None:
        if (type(self.job_id) is not uuid.UUID or not self.job_id.int
                or type(self.embedding_build_batch_id) is not uuid.UUID
                or not self.embedding_build_batch_id.int
                or type(self.embedding_record_ids) is not tuple
                or any(type(value) is not uuid.UUID or not value.int
                       for value in self.embedding_record_ids)
                or len(set(self.embedding_record_ids))
                != len(self.embedding_record_ids)):
            raise RAGEmbeddingBatchWorkerError()
        if self.state == "BATCH_SUCCEEDED":
            if not self.embedding_record_ids or self.error_code is not None:
                raise RAGEmbeddingBatchWorkerError()
            return
        if self.state in {"BUILD_FAILED", "RECONCILIATION_PENDING"}:
            if (self.embedding_record_ids
                    or type(self.error_code) is not str
                    or re.fullmatch(
                        r"[A-Z][A-Z0-9_]{0,63}", self.error_code,
                    ) is None):
                raise RAGEmbeddingBatchWorkerError()
            return
        raise RAGEmbeddingBatchWorkerError()


class _Sender(Protocol):
    def send_once(
        self, *, envelope: AIEmbeddingEnvelope, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> SentAIEmbeddingResponse: ...


class _Success(Protocol):
    def publish(self, **kwargs: object) -> PublishedRAGEmbeddingBatch: ...


class _Failure(Protocol):
    def publish(self, **kwargs: object) -> PublishedRAGEmbeddingBatchFailure: ...


class RAGEmbeddingBatchOneShotWorker:
    """Send, parse and publish one batch; never replay uncertain work."""

    def __init__(self, *, sender: _Sender, success: _Success,
                 failure: _Failure) -> None:
        if any(value is None for value in (sender, success, failure)):
            raise ValueError("RAG Embedding batch Worker dependencies required")
        self._sender = sender
        self._success = success
        self._failure = failure

    def run_once(
        self, *, envelope: AIEmbeddingEnvelope,
        job_id: uuid.UUID, fencing_token: int, worker_ref: str,
    ) -> RAGEmbeddingBatchWorkerCycle:
        if (type(envelope) is not AIEmbeddingEnvelope
                or type(job_id) is not uuid.UUID or not job_id.int
                or type(fencing_token) is not int or fencing_token < 1
                or type(worker_ref) is not str or not worker_ref.strip()):
            raise RAGEmbeddingBatchWorkerError()
        try:
            envelope.__post_init__()
            sent = self._sender.send_once(
                envelope=envelope, job_id=job_id,
                fencing_token=fencing_token, worker_ref=worker_ref,
            )
            if type(sent) is not SentAIEmbeddingResponse:
                if isinstance(sent, SentAIEmbeddingResponse):
                    sent.close()
                raise RAGEmbeddingBatchWorkerError()
            sent.__post_init__()
        except AIEmbeddingSendError as error:
            if (error.code == "AI_EMBEDDING_PROVIDER_REJECTED"
                    and error.authorized_send is not None):
                return self._close_failure(
                    envelope=envelope, send=error.authorized_send,
                    job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                    phase=RAGEmbeddingBatchFailurePhase.PROVIDER_REJECTED,
                )
            return self._pending(
                envelope, job_id,
                "RAG_PROVIDER_OUTCOME_UNKNOWN"
                if error.provider_outcome_unknown else error.code,
            )
        except RAGEmbeddingBatchWorkerError:
            raise
        except Exception:
            return self._pending(
                envelope, job_id, "RAG_EMBEDDING_SEND_UNAVAILABLE",
            )

        with sent:
            try:
                parsed = parse_embedding_response(
                    response=sent.response, envelope=envelope,
                    route=sent.authorization.route,
                )
            except AIEmbeddingResponseError:
                return self._close_failure(
                    envelope=envelope, send=sent.authorization,
                    job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                    phase=RAGEmbeddingBatchFailurePhase.RESPONSE_INVALID,
                    response_fingerprint=(
                        sent.response.observation.response_fingerprint
                    ),
                )
            except Exception:
                return self._pending(
                    envelope, job_id, "RAG_EMBEDDING_RESPONSE_UNAVAILABLE",
                )
            try:
                result = self._success.publish(
                    envelope=envelope, send=sent.authorization,
                    parsed=parsed, job_id=job_id,
                    fencing_token=fencing_token, worker_ref=worker_ref,
                )
                if (type(result) is not PublishedRAGEmbeddingBatch
                        or result.embedding_build_batch_id
                        != envelope.embedding_build_batch_id
                        or len(result.embedding_record_ids)
                        != envelope.record_count):
                    raise RAGEmbeddingBatchSuccessError()
                result.__post_init__()
                return RAGEmbeddingBatchWorkerCycle(
                    "BATCH_SUCCEEDED", job_id,
                    envelope.embedding_build_batch_id,
                    result.embedding_record_ids,
                )
            except RAGEmbeddingBatchSuccessError as error:
                return self._pending(envelope, job_id, error.code)
            except Exception:
                return self._pending(
                    envelope, job_id, "RAG_EMBEDDING_RESULT_NOT_PUBLISHED",
                )

    def _close_failure(
        self, *, envelope: AIEmbeddingEnvelope, send: object,
        job_id: uuid.UUID, fencing_token: int, worker_ref: str,
        phase: RAGEmbeddingBatchFailurePhase,
        response_fingerprint: bytes | None = None,
    ) -> RAGEmbeddingBatchWorkerCycle:
        try:
            result = self._failure.publish(
                envelope=envelope, send=send, job_id=job_id,
                fencing_token=fencing_token, worker_ref=worker_ref,
                phase=phase, response_fingerprint=response_fingerprint,
            )
            if (type(result) is not PublishedRAGEmbeddingBatchFailure
                    or result.embedding_build_batch_id
                    != envelope.embedding_build_batch_id):
                raise RAGEmbeddingBatchFailureError()
            result.__post_init__()
            return RAGEmbeddingBatchWorkerCycle(
                "BUILD_FAILED", job_id,
                envelope.embedding_build_batch_id,
                error_code=result.error_code,
            )
        except RAGEmbeddingBatchFailureError as error:
            return self._pending(envelope, job_id, error.code)
        except Exception:
            return self._pending(
                envelope, job_id,
                "RAG_EMBEDDING_FAILURE_NOT_PUBLISHED",
            )

    @staticmethod
    def _pending(
        envelope: AIEmbeddingEnvelope, job_id: uuid.UUID, error_code: str,
    ) -> RAGEmbeddingBatchWorkerCycle:
        return RAGEmbeddingBatchWorkerCycle(
            "RECONCILIATION_PENDING", job_id,
            envelope.embedding_build_batch_id,
            error_code=error_code,
        )
