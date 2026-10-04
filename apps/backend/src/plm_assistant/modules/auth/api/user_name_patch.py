"""Opt-in AUTH_USER_PATCH; name-only, current authority and strong If-Match."""
from uuid import UUID
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie, _csrf_header, _session_failure
from .user_create import _body
from .user_detail import _public
from ..application.session_service import SessionError
from ..application.user_name_patch import PatchUserName, UserNamePatchError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def create_user_name_patch_router(*, sessions, writes, origins):
    if any(v is None for v in (sessions, writes, origins)):
        raise ValueError('Current User patch dependencies required')
    router = APIRouter()

    @router.patch('/api/v1/admin/users/{user_id}', operation_id='AUTH_USER_PATCH')
    async def patch(user_id: UUID, request: Request):
        headers = tuple(request.scope.get('headers', ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError('AUTH_CSRF_INVALID') from None
        if request.url.query:
            raise ApplicationError('REQUEST_MALFORMED')
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        expected = parse_if_match(headers)
        if not user_id.int:
            raise ApplicationError('RESOURCE_NOT_FOUND')
        types = [v for k, v in headers if k.lower() == b'content-type']
        if len(types) != 1 or types[0].split(b';', 1)[0].strip().lower() != b'application/json':
            raise ApplicationError('REQUEST_MALFORMED')
        body = await _body(request)
        if type(body) is not dict or set(body) != {'username'} or type(body['username']) is not str:
            raise ApplicationError('REQUEST_MALFORMED')
        try:
            view = await run_in_threadpool(writes.patch, PatchUserName(token, csrf,
                UUID(request.state.trace_id), user_id, expected, body['username']))
            data = _public(view, user_id)
            if view.lock_version not in (expected, expected + 1):
                raise ApplicationError('SYSTEM_UNAVAILABLE')
        except UserNamePatchError as exc:
            code = {'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND', 'RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'CONFLICT_VERSION':'CONFLICT_VERSION', 'CONFLICT_DUPLICATE':'CONFLICT_DUPLICATE',
                'VALIDATION_FAILED':'VALIDATION_FAILED', 'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED'
                }.get(exc.code, 'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse(dict(data=data, trace_id=request.state.trace_id), headers={
            'ETag':data['etag'], 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})
    return router
