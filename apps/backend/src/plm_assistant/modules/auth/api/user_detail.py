"""Opt-in frozen User management GET, safe metadata and current authority."""
from datetime import timezone
from uuid import UUID
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie
from ..application.session_service import SessionError
from ..application.user_read import UserGetQuery, UserReadView, UserReadError
from plm_assistant.modules.platform.application.errors import ApplicationError


def _public(view, user_id):
    if type(view) is not UserReadView:raise ValueError('Invalid User metadata')
    view.__post_init__()
    if view.user_id!=user_id:raise ValueError('User binding mismatch')
    stamp=lambda value:value.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    return dict(user_id=str(view.user_id),username_display=view.username_display,
        account_state=view.account_state,deployment_role=view.deployment_role,
        credential_version=view.credential_version,created_at=stamp(view.created_at),
        updated_at=stamp(view.updated_at),etag=f'"v{view.lock_version}"')


def create_user_detail_router(*,sessions,reads,origins):
    if any(v is None for v in (sessions,reads,origins)):raise ValueError('Current User read dependencies required')
    router=APIRouter()
    @router.get('/api/v1/admin/users/{user_id}')
    async def detail(user_id:UUID,request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted_host(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token=_session_cookie(headers)
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        if not user_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        try:await run_in_threadpool(sessions.validate,token)
        except SessionError:raise ApplicationError('AUTH_SESSION_EXPIRED') from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        try:
            view=await run_in_threadpool(reads.get,UserGetQuery(token,user_id,UUID(request.state.trace_id)))
            data=_public(view,user_id)
        except UserReadError as exc:
            code={'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED','VALIDATION_FAILED':'VALIDATION_FAILED'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse(dict(data=data,trace_id=request.state.trace_id),headers={
            'ETag':data['etag'],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    return router
