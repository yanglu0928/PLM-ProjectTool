"""Read-only, licensed DeploymentAdmin Installation detail HTTP boundary."""
from __future__ import annotations

import uuid
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plugin.application.installation_metadata import (
    PluginInstallationMetadataError,
    PluginInstallationMetadataQuery,
    PluginInstallationMetadataService,
    PluginInstallationMetadataView,
)


def _public(view: PluginInstallationMetadataView) -> dict[str, object]:
    if type(view) is not PluginInstallationMetadataView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plugin_installation_id": str(view.plugin_installation_id),
        "plugin_package_id": str(view.plugin_package_id),
        "plugin_id": view.plugin_id,
        "plugin_name": view.plugin_name,
        "plugin_version": view.plugin_version,
        "package_sha256": view.package_sha256,
        "package_state": view.package_state,
        "plugin_api_version": view.plugin_api_version,
        "supported_os": list(view.supported_os),
        "architecture": view.architecture,
        "operations": [{
            "operation_id": item.operation_id,
            "output_types": list(item.output_types),
            "plugin_api_version": item.plugin_api_version,
        } for item in view.operations],
        "installation_state": view.installation_state,
        "compatibility_state": view.compatibility_state,
        "runtime_snapshot": view.runtime_snapshot,
        "enabled_operations": list(view.enabled_operations),
        "lock_version": view.lock_version,
        "etag": view.etag,
    }


def _error(exc: PluginInstallationMetadataError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_plugin_installation_metadata_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    installations: PluginInstallationMetadataService,
) -> APIRouter:
    if any(item is None for item in (sessions, origins, installations)):
        raise ValueError("session, Installation metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/plugins/installations/{installation_id}")
    async def get_installation(
        installation_id: uuid.UUID, request: Request,
    ) -> JSONResponse:
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
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            trace_id = uuid.UUID(str(request.state.trace_id))
            view = await run_in_threadpool(
                installations.get,
                PluginInstallationMetadataQuery(token, trace_id),
                installation_id,
            )
        except PluginInstallationMetadataError as exc:
            raise _error(exc) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _public(view), "trace_id": str(trace_id)},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
