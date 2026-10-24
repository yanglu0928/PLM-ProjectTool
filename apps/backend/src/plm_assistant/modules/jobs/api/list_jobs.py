"""Optional frozen Job lists; opaque cursor and current source authority on every page."""
import re
from uuid import UUID
from dataclasses import replace
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_list import JobListQuery, JobListPage
from ..application.authorized_read import JobGetQuery, JobReadError
from .read_detail import _public

_SIZE = re.compile(r'[1-9][0-9]{0,2}\Z', re.ASCII)


def create_job_list_router(*, reads, origins, cursors):
    if any(v is None for v in (reads, origins, cursors)): raise ValueError('Actual Job list dependencies required')
    router = APIRouter()
    async def list_for(request, project_id):
        headers = tuple(request.scope.get('headers', ()))
        try: origins.require_trusted_host(headers)
        except LoginOriginError: raise ApplicationError('AUTH_CSRF_INVALID') from None
        token = _session_cookie(headers)
        if project_id is not None and not project_id.int: raise ApplicationError('RESOURCE_NOT_FOUND')
        entries = list(request.query_params.multi_items())
        if len(entries) > 3 or len({key for key, _ in entries}) != len(entries) or any(key not in {'page_size', 'scope', 'cursor'} for key, _ in entries):
            raise ApplicationError('REQUEST_MALFORMED')
        params = dict(entries); raw_size = params.get('page_size', '50')
        if _SIZE.fullmatch(raw_size) is None or int(raw_size) > 200: raise ApplicationError('VALIDATION_FAILED')
        try:
            query = JobListQuery(token, project_id, UUID(request.state.trace_id), int(raw_size), scope=params.get('scope'))
            if 'cursor' in params: query = replace(query, before=cursors.decode(params['cursor'], query=query))
            page = await run_in_threadpool(reads.list, query)
            if type(page) is not JobListPage: raise ValueError()
            page.__post_init__()
            if len(page.items) > query.page_size: raise ValueError()
            items = []
            for item in page.items:
                if query.scope is not None and item.facts.scope != query.scope: raise ValueError()
                items.append(_public(item, JobGetQuery(token, project_id, query.trace_id, item.facts.job_id)))
            cursor = cursors.encode(query=query, before=page.next_position) if page.has_more else None
        except ApplicationError: raise
        except JobReadError as exc:
            code = {'AUTH_ACCESS_DENIED': 'AUTH_SESSION_EXPIRED', 'RESOURCE_NOT_FOUND': 'RESOURCE_NOT_FOUND',
                'LICENSE_OPERATION_DENIED': 'LICENSE_OPERATION_DENIED', 'VALIDATION_FAILED': 'VALIDATION_FAILED'}.get(exc.code, 'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except Exception: raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse({'data': {'items': items, 'next_cursor': cursor, 'has_more': page.has_more}, 'trace_id': request.state.trace_id},
            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @router.get('/api/v1/projects/{project_id}/jobs')
    async def project_list(project_id: UUID, request: Request): return await list_for(request, project_id)

    @router.get('/api/v1/admin/jobs')
    async def admin_list(request: Request): return await list_for(request, None)

    return router
