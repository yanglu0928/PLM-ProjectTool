"""CSRF/If-Match/Idempotency protected PluginInstallation disable command."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionPrincipal, SessionService,
)
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plugin.application.activation_owner import DisablePluginInstallationCommand
from plm_assistant.modules.plugin.application.installation_disable import (
    PluginInstallationDisableError, PluginInstallationDisableResult,
    PluginInstallationDisableService,
)


def _public(result: PluginInstallationDisableResult) -> dict[str, object]:
    if type(result) is not PluginInstallationDisableResult:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    if (result.installation_state != "DISABLED"
            or result.result_lock_version not in (
                result.expected_lock_version, result.expected_lock_version + 1,
            )
            or result.changed != (
                result.result_lock_version == result.expected_lock_version + 1
            )):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plugin_installation_id": str(result.plugin_installation_id),
        "installation_state": result.installation_state,
        "enabled_operations": [],
        "lock_version": result.result_lock_version,
        "etag": f'"v{result.result_lock_version}"',
    }


def _error(exc: PluginInstallationDisableError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_plugin_installation_disable_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    disables: PluginInstallationDisableService,
) -> APIRouter:
    if any(item is None for item in (sessions, origins, disables)):
        raise ValueError("Plugin installation disable dependencies are required")
    router = APIRouter()

    @router.post(
        "/api/v1/admin/plugins/installations/{installation_id}:disable",
        operation_id="PLUGIN_DISABLE",
    )
    async def disable_installation(
        installation_id: uuid.UUID, request: Request,
    ) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers),
            _idempotency_header(headers),
        )
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(principal) is not SessionPrincipal
                or type(principal.user_id) is not uuid.UUID
                or principal.user_id.int == 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        expected = parse_if_match(headers)
        if installation_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            trace_id = uuid.UUID(str(request.state.trace_id))
            result = await run_in_threadpool(
                disables.disable,
                DisablePluginInstallationCommand(
                    installation_id, expected, principal.user_id, trace_id,
                ),
                session_token=token, csrf_token=csrf, idempotency_key=key,
            )
        except PluginInstallationDisableError as exc:
            raise _error(exc) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        public = _public(result)
        return JSONResponse(
            {"data": public, "trace_id": str(trace_id)},
            headers={
                "ETag": public["etag"], "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
