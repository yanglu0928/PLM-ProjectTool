"""Optional User management list, fresh authority and protected position."""
import re
from dataclasses import replace
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie
from .user_detail import _public
from ..application.user_list import UserListQuery,UserListPage
from ..application.user_read import UserReadError
from ..application.session_service import SessionError
from plm_assistant.modules.platform.application.errors import ApplicationError

_SIZE=re.compile(r'[1-9][0-9]{0,2}\Z',re.ASCII)


def create_user_list_router(*,sessions,reads,origins,cursors):
    if any(v is None for v in (sessions,reads,origins,cursors)):raise ValueError('Current User list dependencies required')
    router=APIRouter()
    @router.get('/api/v1/admin/users')
    async def list_users(request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted_host(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token=_session_cookie(headers)
        entries=list(request.query_params.multi_items())
        if (len(entries)>2 or len({key for key,_ in entries})!=len(entries)
            or any(key not in {'page_size','cursor'} for key,_ in entries)):raise ApplicationError('REQUEST_MALFORMED')
        params=dict(entries);size=params.get('page_size','50')
        if _SIZE.fullmatch(size) is None or int(size)>200:raise ApplicationError('VALIDATION_FAILED')
        try:await run_in_threadpool(sessions.validate,token)
        except SessionError:raise ApplicationError('AUTH_SESSION_EXPIRED') from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        try:
            query=UserListQuery(token,UUID(request.state.trace_id),int(size))
            if 'cursor' in params:query=replace(query,before=cursors.decode(params['cursor'],query=query))
            page=await run_in_threadpool(reads.list,query)
            if type(page) is not UserListPage:raise ValueError()
            page.__post_init__()
            if (len(page.items)>query.page_size or page.has_more and len(page.items)!=query.page_size
                or query.before is not None and any((item.created_at,item.user_id)>=query.before for item in page.items)):raise ValueError()
            items=[_public(item,item.user_id) for item in page.items]
            cursor=cursors.encode(query=query,before=page.next_position) if page.has_more else None
        except ApplicationError:raise
        except UserReadError as exc:
            code={'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND','LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED',
                'VALIDATION_FAILED':'VALIDATION_FAILED'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse(dict(data=dict(items=items,next_cursor=cursor,has_more=page.has_more),trace_id=request.state.trace_id),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    return router
