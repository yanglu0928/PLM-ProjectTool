"""Single ordered boundary from post-Begin facts to one Provider request."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError,
    SecretConsumer,
    SecretRef,
    SecretResolver,
)
from plm_assistant.modules.platform.application.trace_context import trace_scope

from .provider_execution_contract import (
    AIProviderAdapterPort,
    AIProviderExecutionError,
    AIProviderResponse,
    AIProviderSendProof,
)
from .provider_execution_pre_send import (
    AIProviderPreSendError,
    AIProviderPreSendService,
    AuthorizedAIProviderSend,
)
from .provider_send_fence import (
    AITaskProviderSendFenceError,
    AITaskProviderSendFenceService,
)
from .task_invocation_begin import BegunAITaskInvocation
from .task_invocation_prepare import PreparedAITaskInvocation


class AITaskProviderSendError(RuntimeError):
    def __init__(
        self, code: str = "AI_PROVIDER_SEND_UNAVAILABLE", *,
        provider_outcome_unknown: bool = False,
    ) -> None:
        self.code = code
        self.provider_outcome_unknown = provider_outcome_unknown
        super().__init__(code)


class AITaskProviderSecretAuditScopePort(Protocol):
    def bind(
        self, prepared: PreparedAITaskInvocation,
        send: AuthorizedAIProviderSend,
    ) -> AbstractContextManager[None]: ...


class AITaskProviderSendService:
    """Authorize twice around exact Secret access, then immediately send once."""

    def __init__(
        self, *, pre_send: AIProviderPreSendService,
        secrets: SecretResolver, adapter: AIProviderAdapterPort,
        access_audit_scope: AITaskProviderSecretAuditScopePort,
        send_fence: AITaskProviderSendFenceService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            pre_send, secrets, adapter, access_audit_scope, send_fence,
        )):
            raise ValueError("AI Task Provider send dependencies required")
        self._pre_send = pre_send
        self._secrets = secrets
        self._adapter = adapter
        self._audit_scope = access_audit_scope
        self._send_fence = send_fence
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def send_once(
        self, *, prepared: PreparedAITaskInvocation,
        begun: BegunAITaskInvocation, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> AIProviderResponse:
        if (type(prepared) is not PreparedAITaskInvocation
                or type(begun) is not BegunAITaskInvocation
                or type(job_id) is not uuid.UUID or not job_id.int
                or type(fencing_token) is not int or fencing_token < 1
                or type(worker_ref) is not str or not worker_ref.strip()):
            raise AITaskProviderSendError("AI_PROVIDER_SEND_NOT_AUTHORIZED")

        response: object | None = None
        handed_off = False
        fenced = False

        def authorize() -> AuthorizedAIProviderSend:
            now = self._clock()
            if (not isinstance(now, datetime) or now.tzinfo is None
                    or now.utcoffset() is None):
                raise AITaskProviderSendError(
                    "AI_PROVIDER_SEND_NOT_AUTHORIZED",
                )
            return self._pre_send.authorize(
                prepared=prepared, begun=begun, job_id=job_id,
                fencing_token=fencing_token, worker_ref=worker_ref,
                now=now.astimezone(timezone.utc),
            )

        try:
            initial = authorize()
            with ExitStack() as stack:
                try:
                    stack.enter_context(
                        self._audit_scope.bind(prepared, initial),
                    )
                    stack.enter_context(trace_scope(str(prepared.grant.trace_id)))
                except Exception:
                    raise AITaskProviderSendError(
                        "AI_PROVIDER_SECRET_UNAVAILABLE",
                    ) from None
                with self._secrets.use(
                    SecretRef(initial.route.secret_ref),
                    SecretConsumer.AI_PROVIDER_ADAPTER,
                    expected_version_id=initial.route.secret_version_id,
                ) as key:
                    final = authorize()
                    self._require_stable(initial, final)
                    self._send_fence.fence(
                        prepared=prepared, begun=begun, send=final,
                        job_id=job_id, fencing_token=fencing_token,
                        worker_ref=worker_ref, now=self._clock(),
                    )
                    fenced = True
                    response = self._adapter.send(
                        route=final.route, proof=final.proof,
                        envelope=prepared.envelope, key=key,
                    )
                    if type(response) is not AIProviderResponse:
                        if isinstance(response, AIProviderResponse):
                            response.close()
                        raise AITaskProviderSendError(
                            "AI_PROVIDER_RESPONSE_INVALID",
                        )
            handed_off = True
            return response
        except AITaskProviderSendError as exc:
            if fenced and not exc.provider_outcome_unknown:
                raise AITaskProviderSendError(
                    "AI_PROVIDER_OUTCOME_UNKNOWN",
                    provider_outcome_unknown=True,
                ) from None
            raise
        except AIProviderPreSendError:
            raise AITaskProviderSendError(
                "AI_PROVIDER_SEND_NOT_AUTHORIZED",
            ) from None
        except AITaskProviderSendFenceError:
            raise AITaskProviderSendError(
                "AI_PROVIDER_SEND_NOT_AUTHORIZED",
            ) from None
        except SecretAccessError:
            raise AITaskProviderSendError(
                "AI_PROVIDER_SECRET_UNAVAILABLE",
            ) from None
        except AIProviderExecutionError as exc:
            raise AITaskProviderSendError(
                "AI_PROVIDER_OUTCOME_UNKNOWN" if fenced else exc.code,
                provider_outcome_unknown=fenced,
            ) from None
        except Exception:
            raise AITaskProviderSendError(
                "AI_PROVIDER_OUTCOME_UNKNOWN" if fenced
                else "AI_PROVIDER_SEND_UNAVAILABLE",
                provider_outcome_unknown=fenced,
            ) from None
        finally:
            if not handed_off and isinstance(response, AIProviderResponse):
                response.close()

    @staticmethod
    def _require_stable(
        initial: AuthorizedAIProviderSend,
        final: AuthorizedAIProviderSend,
    ) -> None:
        if (type(initial) is not AuthorizedAIProviderSend
                or type(final) is not AuthorizedAIProviderSend
                or initial.route != final.route
                or not AITaskProviderSendService._same_proof_identity(
                    initial.proof, final.proof,
                )):
            raise AITaskProviderSendError("AI_PROVIDER_SEND_FACTS_CHANGED")

    @staticmethod
    def _same_proof_identity(
        left: AIProviderSendProof, right: AIProviderSendProof,
    ) -> bool:
        if (type(left) is not AIProviderSendProof
                or type(right) is not AIProviderSendProof):
            return False
        return (
            left.ai_task_id == right.ai_task_id
            and left.ai_invocation_id == right.ai_invocation_id
            and left.job_id == right.job_id
            and left.attempt_no == right.attempt_no
            and left.fencing_token == right.fencing_token
            and left.content_plan_id == right.content_plan_id
            and left.authorization_ref == right.authorization_ref
            and left.grant_fingerprint == right.grant_fingerprint
            and left.route_fingerprint == right.route_fingerprint
            and left.payload_fingerprint == right.payload_fingerprint
            and left.payload_bytes == right.payload_bytes
            and left.input_tokens == right.input_tokens
        )
