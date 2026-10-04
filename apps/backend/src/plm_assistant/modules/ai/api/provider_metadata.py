"""Opt-in licensed DeploymentAdmin Provider metadata GET/LIST HTTP boundary."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.provider_metadata import (
    AIProviderMetadataError, AIProviderMetadataPage, AIProviderMetadataQuery,
    AIProviderMetadataService, AIProviderMetadataView,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_MASK = re.compile(r"\*{4}[0-9a-f]{8}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _public(view: AIProviderMetadataView) -> dict[str, object]:
    if (type(view) is not AIProviderMetadataView
            or _MASK.fullmatch(view.secret_ref_masked) is None
            or _ETAG.fullmatch(view.etag) is None
            or view.state not in {"CONFIGURED", "ACTIVE", "SUSPENDED", "RETIRED"}
            or type(view.config_version) is not int or view.config_version < 1):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "provider_id": str(view.provider_id), "kind": view.kind.value,
        "display_name": view.display_name,
        "endpoint_policy_ref": view.endpoint_policy_ref,
        "data_region": view.data_region, "egress_class": view.egress_class,
        "capabilities": sorted(capability.value for capability in view.capabilities),
        "secret_ref_masked": view.secret_ref_masked,
        "state": view.state, "config_version": view.config_version,
        "etag": view.etag,
    }


def _error(exc: AIProviderMetadataError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy) -> AIProviderMetadataQuery:
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
    return AIProviderMetadataQuery(token, uuid.UUID(request.state.trace_id))


def create_ai_provider_read_router(*, sessions: SessionService,
                                   providers: AIProviderMetadataService,
                                   origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, providers, origins)):
        raise ValueError("session, Provider metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/ai/providers")
    async def list_ai_providers(request: Request) -> JSONResponse:
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
            page = await run_in_threadpool(
                providers.list_page, query, page_size=int(raw_size),
                cursor=params.get("cursor"),
            )
        except AIProviderMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not AIProviderMetadataPage
                or len(page.items) > int(raw_size)
                or type(page.has_more) is not bool
                or (page.has_more != (page.next_cursor is not None))):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"items": [_public(item) for item in page.items],
                      "next_cursor": page.next_cursor, "has_more": page.has_more},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/api/v1/admin/ai/providers/{provider_id}")
    async def get_ai_provider(provider_id: uuid.UUID, request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(providers.get, query, provider_id)
        except AIProviderMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
