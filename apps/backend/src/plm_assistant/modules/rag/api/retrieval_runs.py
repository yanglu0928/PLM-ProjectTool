"""Strict opt-in HTTP contract for project RetrievalRun create and reads."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.egress import _canonical_uuid, _read_json
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header,
    _idempotency_header,
    _session_cookie,
    _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.rag.application.create_retrieval import (
    CreateProjectRetrieval,
    CreatedProjectRetrieval,
    RAGRetrievalCreateError,
    RAGRetrievalCreateService,
)
from plm_assistant.modules.rag.application.retrieval_read import (
    GetRAGRetrieval,
    RAGContextBundleView,
    RAGRetrievalReadError,
    RAGRetrievalReadService,
    RAGRetrievalResultView,
    RAGRetrievalRunView,
)


_CREATE_FIELDS = frozenset({
    "query", "metadata_filter", "project_index_ref", "global_index_ref",
    "retrieval_policy_ref", "rerank_policy_ref", "top_k",
})


def _stamp(value: datetime | None) -> str | None:
    return (None if value is None else value.astimezone(timezone.utc)
            .isoformat().replace("+00:00", "Z"))


def _create_command(body: object, *, token: bytes, csrf: bytes,
                    trace_id: uuid.UUID, project_id: uuid.UUID,
                    idempotency_key: str) -> CreateProjectRetrieval:
    if type(body) is not dict or set(body) != _CREATE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(body["query"]) is not str
            or type(body["metadata_filter"]) is not dict
            or type(body["retrieval_policy_ref"]) is not str
            or type(body["rerank_policy_ref"]) is not str
            or type(body["top_k"]) is not int
            or not 1 <= body["top_k"] <= 100
            or body["global_index_ref"] is not None
            or body["retrieval_policy_ref"] != "fts.project.v1"
            or body["rerank_policy_ref"] != "none.v1"):
        raise ApplicationError("VALIDATION_FAILED")
    return CreateProjectRetrieval(
        token, csrf, trace_id, project_id, body["query"],
        dict(body["metadata_filter"]), _canonical_uuid(body["project_index_ref"]),
        None, body["retrieval_policy_ref"], body["rerank_policy_ref"],
        body["top_k"], idempotency_key,
    )


def _create_error(error: RAGRetrievalCreateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "RAG_ACTIVE_INDEX_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "RAG_METADATA_FILTER_NOT_ALLOWED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def _read_error(error: RAGRetrievalReadError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "RAG_RETRIEVAL_RESULT_NOT_READY": "CONFLICT_STATE",
        "RAG_CONTEXT_NOT_READY": "CONFLICT_STATE",
    }.get(error.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def _run_public(value: RAGRetrievalRunView) -> dict[str, object]:
    if type(value) is not RAGRetrievalRunView:
        raise ValueError("invalid RetrievalRun projection")
    value.__post_init__()
    return {
        "retrieval_run_id": str(value.retrieval_run_id),
        "project_id": str(value.project_id),
        "requested_by": str(value.requested_by),
        "global_index_ref": (None if value.global_index_ref is None
                             else str(value.global_index_ref)),
        "project_index_ref": str(value.project_index_ref),
        "retrieval_policy_ref": value.retrieval_policy_ref,
        "rerank_policy_ref": value.rerank_policy_ref,
        "top_k": value.top_k,
        "rerank_state": value.rerank_state,
        "egress_state": value.egress_state,
        "retrieval_state": value.retrieval_state,
        "quality_flags": list(value.quality_flags),
        "degraded": value.degraded,
        "error_code": value.error_code,
        "job_id": str(value.job_id),
        "trace_id": str(value.trace_id),
        "created_at": _stamp(value.created_at),
        "completed_at": _stamp(value.completed_at),
        "etag": f'"v{value.lock_version}"',
    }


def _result_public(value: RAGRetrievalResultView) -> dict[str, object]:
    if type(value) is not RAGRetrievalResultView:
        raise ValueError("invalid Retrieval result projection")
    value.__post_init__()
    return {
        "retrieval_run_id": str(value.retrieval_run_id),
        "project_id": str(value.project_id),
        "quality_flags": list(value.quality_flags),
        "degraded": value.degraded,
        "completed_at": _stamp(value.completed_at),
        "candidates": [{
            "candidate_id": str(item.candidate_id),
            "rank": item.rank,
            "chunk_id": str(item.chunk_id),
            "document_version_ref": str(item.document_version_ref),
            "parse_result_ref": str(item.parse_result_ref),
            "source_type": item.source_type,
            "source_locator": dict(item.source_locator),
            "retrieval_channel": item.retrieval_channel,
            "final_score_micros": item.final_score_micros,
            "score_parts": [{
                "score_kind": part.score_kind,
                "score_ordinal": part.score_ordinal,
                "raw_score_micros": part.raw_score_micros,
                "normalized_score_micros": part.normalized_score_micros,
                "weight_micros": part.weight_micros,
                "weighted_score_micros": part.weighted_score_micros,
                "score_policy_ref": part.score_policy_ref,
            } for part in item.score_parts],
            "snippet": item.snippet,
        } for item in value.candidates],
    }


def _context_public(value: RAGContextBundleView) -> dict[str, object]:
    if type(value) is not RAGContextBundleView:
        raise ValueError("invalid RAG Context projection")
    value.__post_init__()
    return {
        "context_bundle_id": str(value.context_bundle_id),
        "retrieval_run_id": str(value.retrieval_run_id),
        "project_id": str(value.project_id),
        "context_policy_ref": value.context_policy_ref,
        "bundle_fingerprint": value.bundle_fingerprint.hex(),
        "token_budget": value.token_budget,
        "token_count": value.token_count,
        "created_at": _stamp(value.created_at),
        "items": [{
            "ordinal": item.ordinal,
            "chunk_id": str(item.chunk_id),
            "document_version_ref": str(item.document_version_ref),
            "source_locator": dict(item.source_locator),
            "snippet_start": item.snippet_start,
            "snippet_end": item.snippet_end,
            "token_count": item.token_count,
            "snippet": item.snippet,
        } for item in value.items],
    }


def create_rag_retrieval_router(
    *, sessions: SessionService, creates: RAGRetrievalCreateService,
    reads: RAGRetrievalReadService, origins: LoginOriginPolicy,
) -> APIRouter:
    if any(value is None for value in (sessions, creates, reads, origins)):
        raise ValueError("RAG Retrieval HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/retrieval-runs")
    async def create_run(project_id: uuid.UUID, request: Request) -> JSONResponse:
        if not project_id.int or request.url.query:
            raise ApplicationError(
                "RESOURCE_NOT_FOUND" if not project_id.int else "REQUEST_MALFORMED"
            )
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        command = _create_command(
            await _read_json(request, headers), token=token, csrf=csrf,
            trace_id=uuid.UUID(request.state.trace_id), project_id=project_id,
            idempotency_key=key,
        )
        try:
            result = await run_in_threadpool(creates.create, command)
        except RAGRetrievalCreateError as error:
            raise _create_error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not CreatedProjectRetrieval
                or result.project_id != project_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        result.__post_init__()
        location = (f"/api/v1/projects/{project_id}/retrieval-runs/"
                    f"{result.retrieval_run_id}")
        return JSONResponse(
            {"data": {
                "retrieval_run_id": str(result.retrieval_run_id),
                "job_id": str(result.job_id),
            }, "trace_id": request.state.trace_id},
            status_code=202,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    async def read_value(project_id: uuid.UUID, retrieval_run_id: uuid.UUID,
                         request: Request, *, kind: str) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query or not project_id.int or not retrieval_run_id.int:
            raise ApplicationError(
                "REQUEST_MALFORMED" if request.url.query else "RESOURCE_NOT_FOUND"
            )
        query = GetRAGRetrieval(
            _session_cookie(headers), uuid.UUID(request.state.trace_id),
            project_id, retrieval_run_id,
        )
        try:
            if kind == "run":
                value = await run_in_threadpool(reads.get_run, query)
                if (type(value) is not RAGRetrievalRunView
                        or value.project_id != project_id
                        or value.retrieval_run_id != retrieval_run_id):
                    raise ValueError("RetrievalRun response binding mismatch")
                data = _run_public(value)
                extra = {"ETag": str(data["etag"])}
            elif kind == "result":
                value = await run_in_threadpool(reads.get_result, query)
                if (type(value) is not RAGRetrievalResultView
                        or value.project_id != project_id
                        or value.retrieval_run_id != retrieval_run_id):
                    raise ValueError("Retrieval result response binding mismatch")
                data, extra = _result_public(value), {}
            else:
                value = await run_in_threadpool(reads.get_context, query)
                if (type(value) is not RAGContextBundleView
                        or value.project_id != project_id
                        or value.retrieval_run_id != retrieval_run_id):
                    raise ValueError("RAG Context response binding mismatch")
                data, extra = _context_public(value), {}
        except RAGRetrievalReadError as error:
            raise _read_error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                **extra,
            },
        )

    @router.get("/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}")
    async def get_run(project_id: uuid.UUID, retrieval_run_id: uuid.UUID,
                      request: Request) -> JSONResponse:
        return await read_value(project_id, retrieval_run_id, request, kind="run")

    @router.get(
        "/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/result"
    )
    async def get_result(project_id: uuid.UUID, retrieval_run_id: uuid.UUID,
                         request: Request) -> JSONResponse:
        return await read_value(project_id, retrieval_run_id, request, kind="result")

    @router.get(
        "/api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/context"
    )
    async def get_context(project_id: uuid.UUID, retrieval_run_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        return await read_value(project_id, retrieval_run_id, request, kind="context")

    return router
