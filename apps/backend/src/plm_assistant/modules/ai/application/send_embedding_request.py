"""Single ordered boundary from current RAG facts to one Embedding request."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError,
    SecretConsumer,
    SecretRef,
    SecretResolver,
)
from plm_assistant.modules.platform.application.trace_context import trace_scope

from .embedding_execution_contract import (
    AIEmbeddingEnvelope,
    AIEmbeddingExecutionError,
    AIEmbeddingProviderAdapterPort,
    AIEmbeddingSendProof,
)
from .embedding_pre_send import (
    AIEmbeddingPreSendError,
    AIEmbeddingPreSendService,
    AuthorizedAIEmbeddingSend,
)
from .provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderResponse,
)


class AIEmbeddingSendError(RuntimeError):
    def __init__(self, code: str = "AI_EMBEDDING_SEND_UNAVAILABLE", *,
                 provider_outcome_unknown: bool = False,
                 authorized_send: AuthorizedAIEmbeddingSend | None = None) -> None:
        if (type(provider_outcome_unknown) is not bool
                or (authorized_send is not None
                    and type(authorized_send) is not AuthorizedAIEmbeddingSend)):
            raise ValueError("invalid Embedding send error")
        self.code = code
        self.provider_outcome_unknown = provider_outcome_unknown
        self.authorized_send = authorized_send
        super().__init__(code)


class AIEmbeddingBatchFenceError(RuntimeError):
    def __init__(self, *, committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.committed = committed
        super().__init__("AI_EMBEDDING_BATCH_FENCE_UNAVAILABLE")


class AIEmbeddingSecretAuditScopePort(Protocol):
    def bind(self, envelope: AIEmbeddingEnvelope,
             send: AuthorizedAIEmbeddingSend
             ) -> AbstractContextManager[None]: ...


class AIEmbeddingBatchFencePort(Protocol):
    def fence(self, *, envelope: AIEmbeddingEnvelope,
              send: AuthorizedAIEmbeddingSend, job_id: uuid.UUID,
              fencing_token: int, worker_ref: str,
              now: datetime) -> object: ...


@dataclass(slots=True)
class SentAIEmbeddingResponse:
    """One response bound to the exact second pre-send authorization."""

    response: AIProviderResponse = field(repr=False)
    authorization: AuthorizedAIEmbeddingSend

    def __post_init__(self) -> None:
        if (type(self.response) is not AIProviderResponse
                or type(self.authorization) is not AuthorizedAIEmbeddingSend):
            raise AIEmbeddingSendError()
        self.authorization.__post_init__()

    @property
    def observation(self):
        return self.response.observation

    def view(self):
        return self.response.view()

    def close(self) -> None:
        self.response.close()

    def __enter__(self) -> SentAIEmbeddingResponse:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AIEmbeddingSendService:
    """Authorize twice around Secret access, commit one fence, then send once."""

    def __init__(self, *, pre_send: AIEmbeddingPreSendService,
                 secrets: SecretResolver,
                 adapter: AIEmbeddingProviderAdapterPort,
                 access_audit_scope: AIEmbeddingSecretAuditScopePort,
                 send_fence: AIEmbeddingBatchFencePort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                pre_send, secrets, adapter, access_audit_scope, send_fence)):
            raise ValueError("AI Embedding send dependencies required")
        self._pre_send = pre_send
        self._secrets = secrets
        self._adapter = adapter
        self._audit_scope = access_audit_scope
        self._send_fence = send_fence
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def send_once(self, *, envelope: AIEmbeddingEnvelope,
                  job_id: uuid.UUID, fencing_token: int,
                  worker_ref: str) -> SentAIEmbeddingResponse:
        if (type(envelope) is not AIEmbeddingEnvelope
                or type(job_id) is not uuid.UUID or not job_id.int
                or type(fencing_token) is not int or fencing_token < 1
                or type(worker_ref) is not str or not worker_ref.strip()):
            raise AIEmbeddingSendError("AI_EMBEDDING_SEND_NOT_AUTHORIZED")
        response: object | None = None
        handed_off = False
        fenced = False
        final: AuthorizedAIEmbeddingSend | None = None

        def authorize() -> AuthorizedAIEmbeddingSend:
            now = self._clock()
            if (not isinstance(now, datetime) or now.tzinfo is None
                    or now.utcoffset() is None):
                raise AIEmbeddingSendError(
                    "AI_EMBEDDING_SEND_NOT_AUTHORIZED",
                )
            return self._pre_send.authorize(
                envelope=envelope, job_id=job_id,
                fencing_token=fencing_token, worker_ref=worker_ref,
                now=now.astimezone(timezone.utc),
            )

        try:
            initial = authorize()
            with ExitStack() as stack:
                try:
                    stack.enter_context(self._audit_scope.bind(envelope, initial))
                    stack.enter_context(trace_scope(str(initial.proof.trace_id)))
                except Exception:
                    raise AIEmbeddingSendError(
                        "AI_EMBEDDING_SECRET_UNAVAILABLE",
                    ) from None
                with self._secrets.use(
                    SecretRef(initial.route.secret_ref),
                    SecretConsumer.AI_PROVIDER_ADAPTER,
                    expected_version_id=initial.route.secret_version_id,
                ) as key:
                    final = authorize()
                    self._require_stable(initial, final)
                    now = self._clock()
                    if (not isinstance(now, datetime) or now.tzinfo is None
                            or now.utcoffset() is None):
                        raise AIEmbeddingSendError(
                            "AI_EMBEDDING_SEND_NOT_AUTHORIZED",
                        )
                    self._send_fence.fence(
                        envelope=envelope, send=final, job_id=job_id,
                        fencing_token=fencing_token, worker_ref=worker_ref,
                        now=now.astimezone(timezone.utc),
                    )
                    fenced = True
                    response = self._adapter.send(
                        route=final.route, proof=final.proof,
                        envelope=envelope, key=key,
                    )
                    if type(response) is not AIProviderResponse:
                        if isinstance(response, AIProviderResponse):
                            response.close()
                        raise AIEmbeddingSendError(
                            "AI_EMBEDDING_RESPONSE_INVALID",
                        )
            result = SentAIEmbeddingResponse(response, final)
            handed_off = True
            return result
        except AIEmbeddingSendError as exc:
            if fenced and not exc.provider_outcome_unknown:
                raise AIEmbeddingSendError(
                    "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
                    provider_outcome_unknown=True,
                ) from None
            raise
        except AIEmbeddingPreSendError:
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_SEND_NOT_AUTHORIZED",
            ) from None
        except AIEmbeddingBatchFenceError as exc:
            if exc.committed:
                raise AIEmbeddingSendError(
                    "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN",
                    provider_outcome_unknown=True,
                ) from None
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_SEND_NOT_AUTHORIZED",
            ) from None
        except SecretAccessError:
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_SECRET_UNAVAILABLE",
            ) from None
        except AIEmbeddingExecutionError as exc:
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN" if fenced else exc.code,
                provider_outcome_unknown=fenced,
            ) from None
        except AIProviderExecutionError as exc:
            if fenced and exc.code == "AI_PROVIDER_HTTP_REJECTED":
                raise AIEmbeddingSendError(
                    "AI_EMBEDDING_PROVIDER_REJECTED",
                    authorized_send=final,
                ) from None
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN" if fenced
                else "AI_EMBEDDING_SEND_UNAVAILABLE",
                provider_outcome_unknown=fenced,
            ) from None
        except Exception:
            raise AIEmbeddingSendError(
                "AI_EMBEDDING_PROVIDER_OUTCOME_UNKNOWN" if fenced
                else "AI_EMBEDDING_SEND_UNAVAILABLE",
                provider_outcome_unknown=fenced,
            ) from None
        finally:
            if not handed_off and isinstance(response, AIProviderResponse):
                response.close()

    @staticmethod
    def _require_stable(initial: AuthorizedAIEmbeddingSend,
                        final: AuthorizedAIEmbeddingSend) -> None:
        if (type(initial) is not AuthorizedAIEmbeddingSend
                or type(final) is not AuthorizedAIEmbeddingSend
                or initial.route != final.route
                or not AIEmbeddingSendService._same_proof_identity(
                    initial.proof, final.proof)):
            raise AIEmbeddingSendError("AI_EMBEDDING_SEND_FACTS_CHANGED")

    @staticmethod
    def _same_proof_identity(left: AIEmbeddingSendProof,
                             right: AIEmbeddingSendProof) -> bool:
        if (type(left) is not AIEmbeddingSendProof
                or type(right) is not AIEmbeddingSendProof):
            return False
        return all((
            left.job_id == right.job_id,
            left.embedding_build_id == right.embedding_build_id,
            left.embedding_build_batch_id == right.embedding_build_batch_id,
            left.egress_authorization_ref == right.egress_authorization_ref,
            left.trace_id == right.trace_id,
            left.actor_id == right.actor_id,
            left.scope == right.scope,
            left.project_id == right.project_id,
            left.fencing_token == right.fencing_token,
            left.route_fingerprint == right.route_fingerprint,
            left.source_refs_fingerprint == right.source_refs_fingerprint,
            left.payload_fingerprint == right.payload_fingerprint,
            left.payload_bytes == right.payload_bytes,
            left.input_tokens == right.input_tokens,
        ))
