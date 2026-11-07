"""Opt-in, authorized OutputArtifact reference endpoint."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.output.application.read_artifact import (
    OutputArtifactReadError, OutputArtifactReadQuery, OutputArtifactReadService,
    OutputArtifactReference,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MIME = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z", re.ASCII)


def output_artifact_reference_data(value: object) -> dict[str, object]:
    if (type(value) is not OutputArtifactReference
            or any(type(item) is not uuid.UUID or not item.int for item in (
                value.output_artifact_id, value.output_request_id, value.project_id,
                value.document_id, value.document_version_id))
            or value.artifact_kind not in {"DOCX", "PPTX", "PNG", "JPEG"}
            or type(value.media_type) is not str or _MIME.fullmatch(value.media_type) is None
            or type(value.content_sha256) is not str or _HASH.fullmatch(value.content_sha256) is None
            or type(value.size_bytes) is not int or not 0 <= value.size_bytes <= 134217728):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "output_artifact_id": str(value.output_artifact_id),
        "output_request_id": str(value.output_request_id),
        "project_id": str(value.project_id),
        "document_id": str(value.document_id),
        "document_version_id": str(value.document_version_id),
        "artifact_kind": value.artifact_kind,
        "media_type": value.media_type,
        "content_sha256": value.content_sha256,
        "size_bytes": value.size_bytes,
        "content_url": (
            f"/api/v1/projects/{value.project_id}/documents/{value.document_id}"
            f"/versions/{value.document_version_id}/content"
        ),
    }


def create_output_artifact_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service: OutputArtifactReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, service)):
        raise ValueError("OutputArtifact read HTTP dependencies are required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/output-requests/{output_request_id}/artifact",
    )
    async def get_artifact(project_id: uuid.UUID, output_request_id: uuid.UUID,
                           request: Request) -> JSONResponse:
        try:
            origins.require_trusted_host(tuple(request.scope.get("headers", ())))
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(tuple(request.scope.get("headers", ())))
        try:
            await run_in_threadpool(sessions.validate, token)
        except SessionError:
            raise ApplicationError("AUTH_SESSION_EXPIRED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query or not project_id.int or not output_request_id.int:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            trace_id = uuid.UUID(request.state.trace_id)
            result = await run_in_threadpool(
                service.get_available, OutputArtifactReadQuery(token, trace_id),
                project_id=project_id, output_request_id=output_request_id,
            )
        except OutputArtifactReadError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = output_artifact_reference_data(result)
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    return router
