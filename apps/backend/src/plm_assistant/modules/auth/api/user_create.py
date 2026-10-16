"""Opt-in AUTH_USER_CREATE; password write-only, original safe 201 on replay."""
import json
from uuid import UUID
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from .login_origin_policy import LoginOriginError
from .session import _session_cookie, _csrf_header, _idempotency_header, _session_failure
from .user_detail import _public
from ..application.session_service import SessionError
from ..application.managed_user_create import CreateManagedUser, ManagedUserCreateError
from ..application.user_read import UserReadView
from plm_assistant.modules.platform.application.errors import ApplicationError

MAX_USER_CREATE_BODY=16384


def _pairs(pairs):
    body={}
    for key,value in pairs:
        if key in body:raise ValueError('Duplicate JSON key')
        body[key]=value
    return body


def _constant(_):raise ValueError('Nonstandard JSON constant')


async def _body(request):
    raw=bytearray()
    try:
        async for chunk in request.stream():
            if len(raw)+len(chunk)>MAX_USER_CREATE_BODY:raise ApplicationError('REQUEST_MALFORMED')
            raw.extend(chunk)
        try:return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=_pairs,parse_constant=_constant)
        except (ValueError,UnicodeDecodeError,TypeError,RecursionError):raise ApplicationError('REQUEST_MALFORMED') from None
    finally:raw[:]=b'\x00'*len(raw)


def create_user_create_router(*,sessions,writes,origins):
    if any(v is None for v in (sessions,writes,origins)):raise ValueError('Current User create dependencies required')
    router=APIRouter()
    @router.post('/api/v1/admin/users',operation_id='AUTH_USER_CREATE')
    async def create(request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        token=_session_cookie(headers);csrf=_csrf_header(headers);key=_idempotency_header(headers)
        try:await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
        except SessionError as exc:raise _session_failure(exc) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        types=[v for k,v in headers if k.lower()==b'content-type']
        if len(types)!=1 or types[0].split(b';',1)[0].strip().lower()!=b'application/json':
            raise ApplicationError('REQUEST_MALFORMED')
        body=await _body(request)
        if type(body) is not dict or set(body)!={'username','password'} or any(type(v) is not str for v in body.values()):
            raise ApplicationError('REQUEST_MALFORMED')
        try:password=bytearray(body.pop('password').encode('utf-8',errors='strict'))
        except UnicodeEncodeError:raise ApplicationError('VALIDATION_FAILED') from None
        try:
            if not 1<=len(password)<=1024 or b'\x00' in password:raise ApplicationError('VALIDATION_FAILED')
            result=await run_in_threadpool(writes.create,CreateManagedUser(token,csrf,UUID(request.state.trace_id),
                body['username'],password),idempotency_key=key)
            if (type(result) is not UserReadView or result.account_state!='ENABLED' or result.deployment_role!='NONE'
                or result.credential_version!=1 or result.lock_version!=1):raise ApplicationError('SYSTEM_UNAVAILABLE')
            data=_public(result,result.user_id)
        except ManagedUserCreateError as exc:
            code={'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND','AUTH_USERNAME_CONFLICT':'CONFLICT_DUPLICATE',
                'CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED',
                'VALIDATION_FAILED':'VALIDATION_FAILED'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        finally:password[:]=b'\x00'*len(password);body.clear()
        return JSONResponse(dict(data=data,trace_id=request.state.trace_id),status_code=201,headers={
            'ETag':data['etag'],'Location':'/api/v1/admin/users/'+data['user_id'],
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    return router
