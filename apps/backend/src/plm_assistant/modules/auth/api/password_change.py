"""Opt-in own password change, write-only secrets and current-session Cookie policy."""
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie,_csrf_header,_idempotency_header,_session_failure
from .user_create import _body
from ..application.password_change import ChangePassword,PasswordChangeError
from ..application.password_change_replay import PasswordChangeProof
from ..application.password_change_result import PasswordChangeResult
from ..application.session_service import SessionError,SessionPrincipal
from plm_assistant.modules.platform.application.errors import ApplicationError


def create_password_change_router(*,sessions,writes,origins):
    if any(v is None for v in (sessions,writes,origins)):
        raise ValueError('Actual password change dependencies required')
    router=APIRouter()

    @router.post('/api/v1/auth/password:change',operation_id='AUTH_PASSWORD_CHANGE')
    async def change(request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        token,csrf=_session_cookie(headers),_csrf_header(headers)
        key=_idempotency_header(headers)
        try:
            principal=await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
            if type(principal) is not SessionPrincipal or type(principal.user_id) is not UUID or not principal.user_id.int:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
        except SessionError as exc:raise _session_failure(exc) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        types=[v for k,v in headers if k.lower()==b'content-type']
        if len(types)!=1 or types[0].split(b';',1)[0].strip().lower()!=b'application/json':
            raise ApplicationError('REQUEST_MALFORMED')
        body=await _body(request)
        proof=PasswordChangeProof(bytearray(),bytearray())
        try:
            if type(body) is not dict or set(body)!={'current_password','new_password'} or any(type(v) is not str for v in body.values()):
                raise ApplicationError('REQUEST_MALFORMED')
            try:
                proof.current_password.extend(body.pop('current_password').encode('utf-8',errors='strict'))
                proof.new_password.extend(body.pop('new_password').encode('utf-8',errors='strict'))
            except UnicodeEncodeError:raise ApplicationError('VALIDATION_FAILED') from None
            for secret in (proof.current_password,proof.new_password):
                if not 1<=len(secret)<=1024 or b'\x00' in secret:raise ApplicationError('VALIDATION_FAILED')
            result=await run_in_threadpool(writes.change,ChangePassword(token,csrf,UUID(request.state.trace_id),proof),
                idempotency_key=key)
            if type(result) is not PasswordChangeResult or result.user_id!=principal.user_id:
                raise ApplicationError('SYSTEM_UNAVAILABLE')
            result.__post_init__()
            data=result.public_data()
        except PasswordChangeError as exc:
            code={'AUTH_ACCESS_DENIED':'AUTH_SESSION_EXPIRED','AUTH_INVALID_CREDENTIALS':'AUTH_INVALID_CREDENTIALS',
                'VALIDATION_FAILED':'VALIDATION_FAILED','CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        finally:
            proof.erase()
            if type(body) is dict:body.clear()
        clear_cookie=False
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
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        if clear_cookie:
            response.delete_cookie('plm_session',path='/',secure=request.headers['origin'].startswith('https://'),
                httponly=True,samesite='lax')
        return response
    return router
