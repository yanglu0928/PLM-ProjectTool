"""Frozen Job detail GET; current Owner-bound reader, no cache auth shortcut."""
from datetime import timezone
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_read import JobGetQuery,JobDetail,JobReadError

def _public(value,query):
    if type(value) is not JobDetail:raise ValueError('Invalid Job source')
    value.__post_init__()
    facts,owner=value.facts,value.owner
    if (facts.job_id,facts.project_id)!=(query.job_id,query.project_id):raise ValueError('Job binding mismatch')
    if query.project_id is None and facts.scope=='PROJECT':raise ValueError('Job scope mismatch')
    stamp=lambda v:v.astimezone(timezone.utc).isoformat().replace('+00:00','Z') if v is not None else None
    etag=f'"v{facts.lock_version}"'
    return dict(job_id=str(facts.job_id),job_type=facts.job_type,owner_module=facts.owner_module,
        scope=facts.scope,project_id=str(facts.project_id) if facts.project_id is not None else None,
        state=facts.state,progress=None,checkpoint=None,attempt_count=facts.attempt_count,
        retryable=owner.retryable,error_code=None,
        result_ref=dict(type=owner.result_type,id=str(owner.result_id)) if owner.result_id is not None else None,
        created_at=stamp(facts.created_at),completed_at=stamp(facts.completed_at),etag=etag)

def create_job_detail_router(*,reads,origins):
    if reads is None or origins is None:raise ValueError('Current Job reads and origins required')
    router=APIRouter()
    async def detail(request,project_id,job_id):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted_host(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token=_session_cookie(headers)
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        if not job_id.int or project_id is not None and not project_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        try:
            query=JobGetQuery(token,project_id,UUID(request.state.trace_id),job_id)
            value=await run_in_threadpool(reads.get,query)
            data=_public(value,query)
        except JobReadError as exc:
            code={'AUTH_ACCESS_DENIED':'AUTH_SESSION_EXPIRED','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED','VALIDATION_FAILED':'VALIDATION_FAILED'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        return JSONResponse(dict(data=data,trace_id=request.state.trace_id),headers={
            'ETag':data['etag'],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    @router.get('/api/v1/projects/{project_id}/jobs/{job_id}')
    async def project_detail(project_id:UUID,job_id:UUID,request:Request):
        return await detail(request,project_id,job_id)
    @router.get('/api/v1/admin/jobs/{job_id}')
    async def admin_detail(job_id:UUID,request:Request):
        return await detail(request,None,job_id)
    return router
