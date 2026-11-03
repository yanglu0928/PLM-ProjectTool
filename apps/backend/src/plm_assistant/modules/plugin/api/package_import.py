"""Bounded raw-body HTTP endpoint for signed Plugin package import."""
from __future__ import annotations

import base64
import binascii
import re
import uuid
from collections.abc import Iterator
from typing import Callable

from anyio import from_thread
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyScope, validate_idempotency_key,
)
from plm_assistant.modules.plugin.application.package_archive_inspector import MAX_PACKAGE_BYTES
from plm_assistant.modules.plugin.application.package_import_service import (
    PluginPackageImportError,
    PluginPackageImportService,
    SubmitPluginPackageImport,
)
from plm_assistant.modules.plugin.application.package_import_spool import PluginPackageStageError


_SHA = re.compile(r"[0-9a-f]{64}\\Z", re.ASCII)
_LENGTH = re.compile(r"[1-9][0-9]*\\Z", re.ASCII)
_CHUNK = 1_048_576


def _single_header(headers: tuple[tuple[bytes, bytes], ...], name: bytes) -> bytes:
    values = [value for key, value in headers if key.lower() == name]
    if len(values) != 1:
        raise ApplicationError("REQUEST_MALFORMED")
    return values[0]


def _claims(headers: tuple[tuple[bytes, bytes], ...]) -> tuple[str, int, bytes, bytes, str]:
    try:
        content_type = _single_header(headers, b"content-type").decode("ascii").strip().lower()
        length_text = _single_header(headers, b"content-length").decode("ascii")
        sha_text = _single_header(headers, b"x-content-sha256").decode("ascii")
        signature_text = _single_header(headers, b"x-plugin-signature").decode("ascii")
        signer_key_ref = _single_header(headers, b"x-plugin-signer-key-ref").decode("utf-8", "strict")
        idempotency_key = _single_header(headers, b"idempotency-key").decode("ascii")
    except UnicodeError:
        raise ApplicationError("REQUEST_MALFORMED") from None
    if content_type != "application/octet-stream":
        raise ApplicationError("REQUEST_MALFORMED")
    if (_LENGTH.fullmatch(length_text) is None or len(length_text) > 20
            or _SHA.fullmatch(sha_text) is None):
        raise ApplicationError("VALIDATION_FAILED")
    length = int(length_text)
    if length > MAX_PACKAGE_BYTES:
        raise ApplicationError("FILE_TOO_LARGE")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (ValueError, binascii.Error):
        raise ApplicationError("VALIDATION_FAILED") from None
    if len(signature) != 64 or not signer_key_ref:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        validate_idempotency_key(idempotency_key)
    except IdempotencyError:
        raise ApplicationError("VALIDATION_FAILED") from None
    return idempotency_key, length, bytes.fromhex(sha_text), signature, signer_key_ref


def _chunks(request: Request) -> Iterator[bytes]:
    """Read ASGI body incrementally and split oversized transport chunks."""
    stream = request.stream()

    async def next_chunk() -> bytes:
        return await anext(stream)

    while True:
        try:
            chunk = from_thread.run(next_chunk)
        except StopAsyncIteration:
            return
        if type(chunk) is not bytes:
            raise PluginPackageStageError("VALIDATION_FAILED")
        for offset in range(0, len(chunk), _CHUNK):
            yield chunk[offset:offset + _CHUNK]


def _map_error(code: str) -> str:
    return {
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
        "FILE_TOO_LARGE": "FILE_TOO_LARGE",
        "FILE_INTEGRITY_MISMATCH": "FILE_INTEGRITY_MISMATCH",
        "PLUGIN_PACKAGE_STAGE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
        "JOB_STORE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "AUTH_ACCESS_DENIED": "AUTH_ACCESS_DENIED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
    }.get(code, "SYSTEM_UNAVAILABLE")


def create_plugin_package_import_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service_factory: Callable[[bytes, bytes], PluginPackageImportService],
) -> APIRouter:
    if sessions is None or origins is None or service_factory is None:
        raise ValueError("Plugin package import HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/admin/plugins/packages:import")
    async def import_package(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        actor_id = getattr(principal, "user_id", None)
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        key, length, sha256, signature, signer_key_ref = _claims(headers)
        try:
            scope = IdempotencyScope.from_key(
                actor_id=actor_id, project_id=None,
                operation="V1_PLUGIN_PACKAGE_IMPORT", key=key,
            )
            trace_id = uuid.UUID(str(request.state.trace_id))
            service = service_factory(token, csrf)
            result = await run_in_threadpool(
                service.submit,
                SubmitPluginPackageImport(
                    scope=scope, session_token=token, trace_id=trace_id,
                    declared_length=length, declared_sha256=sha256,
                    detached_signature=signature, signer_key_ref=signer_key_ref,
                    chunks=_chunks(request),
                ),
            )
        except PluginPackageImportError as exc:
            raise ApplicationError(_map_error(exc.code)) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result.job_id) is not uuid.UUID or result.job_id.int == 0
                or type(result.package_upload_id) is not uuid.UUID
                or result.package_upload_id.int == 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            status_code=202,
            content={
                "data": {
                    "job_id": str(result.job_id),
                    "job_type": "PLUGIN_PACKAGE_VERIFY",
                    "status": "QUEUED",
                },
                "trace_id": str(trace_id),
            },
            headers={"Cache-Control": "no-store"},
        )

    return router
