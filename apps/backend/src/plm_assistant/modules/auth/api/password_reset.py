"""Opt-in strict administrator reset with write-only password and own Cookie policy."""
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie,_csrf_header,_idempotency_header,_session_failure
from .user_create import _body
from ..application.password_reset import ResetPassword,PasswordResetError
from ..application.password_reset_replay import PasswordResetProof
from ..application.password_reset_result import PasswordResetResult
from ..application.session_service import SessionError,SessionPrincipal
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def create_password_reset_router(*,sessions,writes,origins):
    if any(v is None for v in (sessions,writes,origins)):raise ValueError('Actual password reset dependencies required')
    router=APIRouter()
    @router.post('/api/v1/admin/users/{user_id}:reset-password',operation_id='AUTH_USER_RESET_PASSWORD')
    async def reset(user_id:UUID,request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        token,csrf=_session_cookie(headers),_csrf_header(headers);key=_idempotency_header(headers)
        try:
            principal=await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
            if type(principal) is not SessionPrincipal or type(principal.user_id) is not UUID or not principal.user_id.int:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
        except SessionError as exc:raise _session_failure(exc) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        expected=parse_if_match(headers)
        if not user_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        types=[v for k,v in headers if k.lower()==b'content-type']
        if len(types)!=1 or types[0].split(b';',1)[0].strip().lower()!=b'application/json':raise ApplicationError('REQUEST_MALFORMED')
        body=await _body(request);proof=PasswordResetProof(bytearray())
        try:
            if (type(body) is not dict or set(body)!={'temporary_password','must_change_password'}
                or type(body['temporary_password']) is not str):raise ApplicationError('REQUEST_MALFORMED')
            if body['must_change_password'] is not True:raise ApplicationError('VALIDATION_FAILED')
            try:proof.temporary_password.extend(body.pop('temporary_password').encode('utf-8',errors='strict'))
            except UnicodeEncodeError:raise ApplicationError('VALIDATION_FAILED') from None
            if not 1<=len(proof.temporary_password)<=1024 or b'\x00' in proof.temporary_password:
                raise ApplicationError('VALIDATION_FAILED')
            result=await run_in_threadpool(writes.reset,ResetPassword(token,csrf,UUID(request.state.trace_id),user_id,
                expected,True,proof),idempotency_key=key)
            if type(result) is not PasswordResetResult:raise ApplicationError('SYSTEM_UNAVAILABLE')
            result.__post_init__()
            if result.user_id!=user_id or result.actor_id!=principal.user_id or result.before_user_version!=expected:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            data=result.public_data();etag=f'"v{result.user_version}"'
        except PasswordResetError as exc:
            code={'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'CONFLICT_VERSION':'CONFLICT_VERSION','CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY',
                'VALIDATION_FAILED':'VALIDATION_FAILED','LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        finally:
            proof.erase()
            if type(body) is dict:body.clear()
        clear_cookie=False
        if user_id==principal.user_id:
            try:
                current=await run_in_threadpool(sessions.validate,token)
                if type(current) is not SessionPrincipal or current.user_id!=principal.user_id:
                    raise ApplicationError('SYSTEM_UNAVAILABLE')
            except SessionError as exc:
                if exc.code=='AUTH_SESSION_EXPIRED':clear_cookie=True
                else:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
            except ApplicationError:raise
            except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        response=JSONResponse(dict(data=data,trace_id=request.state.trace_id),headers={
            'ETag':etag,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        if clear_cookie:
            response.delete_cookie('plm_session',path='/',secure=request.headers['origin'].startswith('https://'),
                httponly=True,samesite='lax')
        return response
    return router
