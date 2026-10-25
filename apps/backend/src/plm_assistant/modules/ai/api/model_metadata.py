"""Opt-in licensed DeploymentAdmin AIModel metadata GET/LIST boundary."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.model_metadata import (
    AIModelMetadataError, AIModelMetadataPage, AIModelMetadataQuery,
    AIModelMetadataService, AIModelMetadataView,
)
from plm_assistant.modules.ai.domain.model_definition import AIModelDefinition, AIModelDefinitionError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_PROFILE = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _public(view: AIModelMetadataView) -> dict[str, object]:
    try:
        if (type(view) is not AIModelMetadataView
                or type(view.quality_profile_refs) is not tuple
                or any(type(value) is not str or _PROFILE.fullmatch(value) is None
                       for value in view.quality_profile_refs)
                or view.state not in {"AVAILABLE", "SUSPENDED", "RETIRED"}
                or type(view.lock_version) is not int or view.lock_version < 0
                or _ETAG.fullmatch(view.etag) is None
                or view.quality_status != "NOT_EVALUATED"):
            raise ValueError()
        AIModelDefinition(
            view.model_id, view.provider_id, view.provider_model_key, view.kind,
            view.revision, view.embedding_dimension, view.structured_output,
            view.context_window_tokens,
        )
    except (AIModelDefinitionError, ValueError, TypeError, AttributeError):
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    return {
        "model_id": str(view.model_id), "provider_id": str(view.provider_id),
        "provider_model_key": view.provider_model_key, "kind": view.kind.value,
        "revision": view.revision, "embedding_dimension": view.embedding_dimension,
        "capabilities": {"structured_output": view.structured_output,
                         "context_window_tokens": view.context_window_tokens},
        "quality_profile_refs": list(view.quality_profile_refs),
        "quality_status": "NOT_EVALUATED", "state": view.state, "etag": view.etag,
    }


def _error(exc: AIModelMetadataError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy) -> AIModelMetadataQuery:
    headers = tuple(request.scope.get("headers", ()))
    try:
        origins.require_trusted_host(headers)
    except LoginOriginError:
        raise ApplicationError("AUTH_CSRF_INVALID") from None
    token = _session_cookie(headers)
    try:
        await run_in_threadpool(sessions.validate, token)
    except SessionError:
        raise ApplicationError("AUTH_SESSION_EXPIRED") from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    return AIModelMetadataQuery(token, uuid.UUID(request.state.trace_id))


def create_ai_model_read_router(*, sessions: SessionService,
                                models: AIModelMetadataService,
                                origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, models, origins)):
        raise ValueError("session, Model metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/ai/models")
    async def list_ai_models(request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            page = await run_in_threadpool(models.list_page, query, page_size=int(raw_size),
                                           cursor=params.get("cursor"))
        except AIModelMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not AIModelMetadataPage or len(page.items) > int(raw_size)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_cursor is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"items": [_public(item) for item in page.items],
                      "next_cursor": page.next_cursor, "has_more": page.has_more},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/api/v1/admin/ai/models/{model_id}")
    async def get_ai_model(model_id: uuid.UUID, request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(models.get, query, model_id)
        except AIModelMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
