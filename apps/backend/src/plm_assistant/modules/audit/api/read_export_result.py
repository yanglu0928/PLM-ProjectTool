"""Opt-in current-authorized published metadata; no files, manifest or paths."""
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_read import AuthorizedAuditReadError
from ..application.export_content import AuditExportContentQuery, AuthorizedAuditExportSource
from .read_events import _error


def _public(source, query):
    if type(source) is not AuthorizedAuditExportSource:
        raise ValueError('Invalid result source')
    source.__post_init__()
    result, coordinate = source.result, source.content.coordinate
    scope = 'DEPLOYMENT' if query.project_id is None else 'PROJECT'
    if (result.export_id, coordinate.scope, coordinate.project_id) != (query.export_id, scope, query.project_id):
        raise ValueError('Result binding mismatch')
    return dict(export_id=str(result.export_id), scope=scope,
                project_id=str(query.project_id) if query.project_id is not None else None,
                published_at=result.published_at.isoformat().replace('+00:00', 'Z'),
                size_bytes=result.byte_count, mime_type=result.mime_type,
                file_sha256=result.file_sha256.hex(), manifest_version=result.manifest_version,
                manifest_sha256=result.manifest_sha256.hex())


def create_audit_export_result_router(*, reads, origins):
    if reads is None or origins is None:
        raise ValueError('Current authorized source reader and origins required')
    router = APIRouter()

    async def detail(request, project_id, export_id):
        headers = tuple(request.scope.get('headers', ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError('AUTH_CSRF_INVALID') from None
        token = _session_cookie(headers)
        if request.url.query:
            raise ApplicationError('REQUEST_MALFORMED')
        if not export_id.int or project_id is not None and not project_id.int:
            raise ApplicationError('RESOURCE_NOT_FOUND')
        try:
            query = AuditExportContentQuery(token, project_id, UUID(request.state.trace_id), export_id)
            source = await run_in_threadpool(reads.get_source, query)
            data = _public(source, query)
        except AuthorizedAuditReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse(dict(data=data, trace_id=request.state.trace_id),
                            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @router.get('/api/v1/projects/{project_id}/audit-exports/{export_id}')
    async def project_result(project_id: UUID, export_id: UUID, request: Request):
        return await detail(request, project_id, export_id)

    @router.get('/api/v1/admin/audit-exports/{export_id}')
    async def deployment_result(export_id: UUID, request: Request):
        return await detail(request, None, export_id)

    return router
