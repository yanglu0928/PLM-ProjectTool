"""Opt-in frozen User enable/disable commands; immutable safe first response."""
from uuid import UUID
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie, _csrf_header, _idempotency_header, _session_failure
from .user_detail import _public
from ..application.session_service import SessionError, SessionPrincipal
from ..application.user_state import ChangeUserState, UserStateError
from ..application.user_state_result import UserStateResult
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def create_user_state_router(*, sessions, writes, origins):
    if any(v is None for v in (sessions, writes, origins)):
        raise ValueError('Current User state dependencies required')
    router = APIRouter()

    async def execute(user_id, request, operation):
        headers = tuple(request.scope.get('headers', ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError('AUTH_CSRF_INVALID') from None
        if request.url.query:
            raise ApplicationError('REQUEST_MALFORMED')
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        key = _idempotency_header(headers)
        try:
            principal = await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
            if type(principal) is not SessionPrincipal or not isinstance(principal.user_id, UUID) or not principal.user_id.int:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
        except SessionError as exc:
            raise _session_failure(exc) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        expected = parse_if_match(headers)
        if not user_id.int:
            raise ApplicationError('RESOURCE_NOT_FOUND')
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError('REQUEST_MALFORMED')
        try:
            method = writes.enable if operation == 'ENABLE' else writes.disable
            result = await run_in_threadpool(method, ChangeUserState(token, csrf,
                UUID(request.state.trace_id), user_id, expected), idempotency_key=key)
            if type(result) is not UserStateResult:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            result.__post_init__()
            if (result.operation != operation or result.expected_version != expected
                or result.actor_id != principal.user_id):
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            data = _public(result.first_view, user_id)
        except UserStateError as exc:
            code = {'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND', 'RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'CONFLICT_STATE':'AUTH_USER_DISABLED', 'CONFLICT_VERSION':'CONFLICT_VERSION',
                'CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY', 'VALIDATION_FAILED':'VALIDATION_FAILED',
                'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED'}.get(exc.code, 'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        clear_cookie = False
        if operation == 'DISABLE' and principal.user_id == user_id:
            try:
                current = await run_in_threadpool(sessions.validate, token)
                if type(current) is not SessionPrincipal or current.user_id != principal.user_id:
                    raise ApplicationError('SYSTEM_UNAVAILABLE')
            except SessionError as exc:
                if exc.code == 'AUTH_SESSION_EXPIRED':
                    clear_cookie = True
                else:
                    raise ApplicationError('SYSTEM_UNAVAILABLE') from None
            except ApplicationError:
                raise
            except Exception:
                raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        response = JSONResponse(dict(data=data, trace_id=request.state.trace_id), headers={
            'ETag':data['etag'], 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})
        if clear_cookie:
            response.delete_cookie('plm_session', path='/', secure=request.headers['origin'].startswith('https://'),
                httponly=True, samesite='lax')
        return response

    @router.post('/api/v1/admin/users/{user_id}:enable', operation_id='AUTH_USER_ENABLE')
    async def enable(user_id: UUID, request: Request):
        return await execute(user_id, request, 'ENABLE')

    @router.post('/api/v1/admin/users/{user_id}:disable', operation_id='AUTH_USER_DISABLE')
    async def disable(user_id: UUID, request: Request):
        return await execute(user_id, request, 'DISABLE')

    return router
