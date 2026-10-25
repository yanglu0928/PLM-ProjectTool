"""Optional frozen PROJECT cancellation, original state/version response only."""
import json
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie,_csrf_header,_idempotency_header,_session_failure
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.cancel_request import RequestProjectJobCancel,JobCancelResult,JobCancelError

def _pairs(items):
    out={}
    for key,value in items:
        if key in out:raise ValueError('duplicate key')
        out[key]=value
    return out
def _constant(_):raise ValueError('nonstandard constant')
async def _reason(request,headers):
    types=[v for k,v in headers if k.lower()==b'content-type']
    if len(types)!=1 or types[0].strip().lower() not in (b'application/json',b'application/json; charset=utf-8'):
        raise ApplicationError('REQUEST_MALFORMED')
    raw=bytearray()
    try:
        async for chunk in request.stream():
            if len(raw)+len(chunk)>8192:raise ApplicationError('REQUEST_MALFORMED')
            raw.extend(chunk)
        try:value=json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=_pairs,parse_constant=_constant)
        except (ValueError,TypeError,RecursionError):raise ApplicationError('REQUEST_MALFORMED') from None
        if type(value) is not dict or set(value)!={'reason'}:raise ApplicationError('REQUEST_MALFORMED')
        return value['reason']
    finally:raw[:]=b'\x00'*len(raw)

def create_project_job_cancel_router(*,sessions,cancellations,origins):
    if any(v is None for v in (sessions,cancellations,origins)):raise ValueError('Current cancellation dependencies required')
    router=APIRouter()
    @router.post('/api/v1/projects/{project_id}/jobs/{job_id}:cancel')
    async def cancel(project_id:UUID,job_id:UUID,request:Request):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token,csrf,key=_session_cookie(headers),_csrf_header(headers),_idempotency_header(headers)
        version=parse_if_match(headers)
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        if not job_id.int or not project_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        try:await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
        except SessionError as exc:raise _session_failure(exc) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        reason=await _reason(request,headers)
        try:
            command=RequestProjectJobCancel(job_id,project_id,token,csrf,UUID(request.state.trace_id),reason,version)
            result=await run_in_threadpool(cancellations.cancel,command,idempotency_key=key)
            if type(result) is not JobCancelResult or result.job_id!=job_id:raise ValueError('Invalid cancellation source')
            result.__post_init__()
        except JobCancelError as exc:
            allowed={'AUTH_SESSION_EXPIRED','AUTH_CSRF_INVALID','RESOURCE_NOT_FOUND','CONFLICT_VERSION','CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED','VALIDATION_FAILED'}
            raise ApplicationError(exc.code if exc.code in allowed else 'SYSTEM_UNAVAILABLE') from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        etag=f'"v{result.lock_version}"'
        return JSONResponse(dict(data=dict(job_id=str(job_id),state=result.state,changed=result.changed,etag=etag,
            status_url=f'/api/v1/projects/{project_id}/jobs/{job_id}'),trace_id=request.state.trace_id),
            headers={'ETag':etag,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    return router
