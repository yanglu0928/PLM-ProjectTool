"""Optional frozen retry paths; opaque authority, original first new Job response."""
import json
from uuid import UUID
from datetime import timezone
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie, _csrf_header, _idempotency_header, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.retry_request import RequestJobRetry, JobRetryResult, JobRetryError
from .cancel import _pairs, _constant

async def _empty_body(request,headers):
    types=[v for k,v in headers if k.lower()==b'content-type']
    if len(types)!=1 or types[0].strip().lower() not in (b'application/json',b'application/json; charset=utf-8'):
        raise ApplicationError('REQUEST_MALFORMED')
    raw=bytearray()
    try:
        async for chunk in request.stream():
            if len(raw)+len(chunk)>1024:raise ApplicationError('REQUEST_MALFORMED')
            raw.extend(chunk)
        try:value=json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=_pairs,parse_constant=_constant)
        except (ValueError,TypeError,RecursionError):raise ApplicationError('REQUEST_MALFORMED') from None
        if type(value) is not dict or value:raise ApplicationError('REQUEST_MALFORMED')
    finally:raw[:]=b'\x00'*len(raw)

def create_job_retry_router(*,sessions,retries,origins):
    if any(v is None for v in (sessions,retries,origins)):raise ValueError('Actual retry HTTP dependencies required')
    router=APIRouter()
    async def retry(request,job_id,project_id):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token,csrf,key=_session_cookie(headers),_csrf_header(headers),_idempotency_header(headers)
        version=parse_if_match(headers)
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        if not job_id.int or project_id is not None and not project_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        try:await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
        except SessionError as exc:raise _session_failure(exc) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        await _empty_body(request,headers)
        try:
            c=RequestJobRetry(job_id,project_id,token,csrf,UUID(request.state.trace_id),version)
            result=await run_in_threadpool(retries.retry,c,idempotency_key=key)
            if type(result) is not JobRetryResult or (result.source_job_id,result.project_id)!=(job_id,project_id):raise ValueError()
            result.__post_init__()
        except JobRetryError as exc:
            allowed={'AUTH_SESSION_EXPIRED','AUTH_CSRF_INVALID','RESOURCE_NOT_FOUND','CONFLICT_VERSION',
                'CONFLICT_IDEMPOTENCY','LICENSE_OPERATION_DENIED','VALIDATION_FAILED','JOB_NOT_RETRYABLE'}
            raise ApplicationError(exc.code if exc.code in allowed else 'SYSTEM_UNAVAILABLE') from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        status=f'/api/v1/projects/{project_id}/jobs/{result.job_id}' if project_id else f'/api/v1/admin/jobs/{result.job_id}'
        return JSONResponse(dict(data=dict(job_id=str(result.job_id),source_job_id=str(job_id),scope=result.scope,
            project_id=str(project_id) if project_id else None,state='PENDING',etag='"v0"',status_url=status,
            accepted_at=result.accepted_at.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')),
            trace_id=request.state.trace_id),status_code=202,
            headers={'ETag':'"v0"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Location':status})
    @router.post('/api/v1/projects/{project_id}/jobs/{job_id}:retry')
    async def project_retry(project_id:UUID,job_id:UUID,request:Request):return await retry(request,job_id,project_id)
    @router.post('/api/v1/admin/jobs/{job_id}:retry')
    async def admin_retry(job_id:UUID,request:Request):return await retry(request,job_id,None)
    return router
