"""Strict optional HTTP alias for one RetrievalRun cancellation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header,
    _idempotency_header,
    _session_cookie,
    _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.jobs.api.cancel import _reason
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.rag.application.retrieval_cancel import (
    CancelledRAGRetrieval,
    RAGRetrievalCancelError,
    RAGRetrievalCancelOwner,
    RequestRAGRetrievalCancel,
)


def create_rag_retrieval_cancel_router(
    *, sessions: SessionService, cancellations: RAGRetrievalCancelOwner,
    origins: LoginOriginPolicy,
) -> APIRouter:
    if any(value is None for value in (sessions, cancellations, origins)):
        raise ValueError("RAG Retrieval cancel HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}:cancel"
    )
    async def cancel_retrieval(
        project_id: uuid.UUID, retrieval_run_id: uuid.UUID, request: Request,
    ) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers),
            _idempotency_header(headers),
        )
        version = parse_if_match(headers)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        if not project_id.int or not retrieval_run_id.int:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        reason = await _reason(request, headers)
        try:
            command = RequestRAGRetrievalCancel(
                retrieval_run_id, project_id, token, csrf,
                uuid.UUID(request.state.trace_id), reason, version,
            )
            result = await run_in_threadpool(
                cancellations.cancel_retrieval, command,
                idempotency_key=key,
            )
            if (type(result) is not CancelledRAGRetrieval
                    or result.project_id != project_id
                    or result.retrieval_run_id != retrieval_run_id):
                raise ValueError("invalid Retrieval cancellation result")
            result.__post_init__()
        except RAGRetrievalCancelError as error:
            allowed = {
                "RESOURCE_NOT_FOUND", "CONFLICT_VERSION",
                "CONFLICT_IDEMPOTENCY", "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED",
            }
            raise ApplicationError(
                error.code if error.code in allowed else "SYSTEM_UNAVAILABLE"
            ) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        etag = f'"v{result.run_lock_version}"'
        base = f"/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}"
        return JSONResponse(
            {"data": {
                "retrieval_run_id": str(retrieval_run_id),
                "job_id": str(result.job_id),
                "state": result.state,
                "changed": result.changed,
                "etag": etag,
                "status_url": base,
            }, "trace_id": request.state.trace_id},
            headers={
                "ETag": etag, "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
