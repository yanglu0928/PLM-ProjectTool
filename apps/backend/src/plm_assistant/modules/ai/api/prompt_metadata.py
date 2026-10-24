"""Opt-in DeploymentAdmin Prompt metadata LIST/GET; no template bodies."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.prompt_metadata import (
    PromptMetadataError, PromptMetadataPage, PromptMetadataQuery,
    PromptMetadataService, PromptMetadataView,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _public(view: PromptMetadataView) -> dict[str, object]:
    try:
        if (type(view) is not PromptMetadataView
                or type(view.template_id) is not uuid.UUID or view.template_id.int == 0
                or type(view.task_type) is not PromptTaskType
                or view.state not in {"DRAFT", "ACTIVE", "RETIRED"}
                or type(view.lock_version) is not int or view.lock_version < 0
                or view.etag != f'"v{view.lock_version}"'):
            raise ValueError()
        active = view.state == "ACTIVE"
        refs = (view.output_schema_ref, view.rag_policy_ref, view.provider_policy_ref)
        hashes = (view.system_template_hash, view.user_template_hash)
        if active:
            if (type(view.active_version_no) is not int or view.active_version_no < 1
                    or type(view.schema_version) is not int or view.schema_version < 1
                    or any(type(value) is not str or _REF.fullmatch(value) is None
                           for value in refs)
                    or any(type(value) is not str or _HASH.fullmatch(value) is None
                           for value in hashes)):
                raise ValueError()
        elif (view.active_version_no is not None or view.schema_version is not None
              or any(value is not None for value in (*refs, *hashes))):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    return {
        "prompt_template_id": str(view.template_id), "task_type": view.task_type.value,
        "state": view.state, "active_version_no": view.active_version_no,
        "output_schema_ref": view.output_schema_ref, "schema_version": view.schema_version,
        "rag_policy_ref": view.rag_policy_ref, "provider_policy_ref": view.provider_policy_ref,
        "system_template_hash": view.system_template_hash,
        "user_template_hash": view.user_template_hash, "etag": view.etag,
    }


def _error(exc: PromptMetadataError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy) -> PromptMetadataQuery:
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
    return PromptMetadataQuery(token, uuid.UUID(request.state.trace_id))


def create_ai_prompt_read_router(*, sessions: SessionService,
                                 prompts: PromptMetadataService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, prompts, origins)):
        raise ValueError("session, Prompt metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/ai/prompt-templates")
    async def list_ai_prompts(request: Request) -> JSONResponse:
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
            page = await run_in_threadpool(prompts.list_page, query, page_size=int(raw_size),
                                           cursor=params.get("cursor"))
        except PromptMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PromptMetadataPage or len(page.items) > int(raw_size)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_cursor is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"items": [_public(item) for item in page.items],
                      "next_cursor": page.next_cursor, "has_more": page.has_more},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/api/v1/admin/ai/prompt-templates/{prompt_template_id:uuid}")
    async def get_ai_prompt(prompt_template_id: uuid.UUID, request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(prompts.get, query, prompt_template_id)
        except PromptMetadataError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
