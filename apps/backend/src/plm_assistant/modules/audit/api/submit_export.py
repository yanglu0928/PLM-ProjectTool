"""Bounded licensed idempotent export acceptance; no long work in HTTP."""
import json
import re
from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie,_csrf_header,_idempotency_header,_session_failure
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.export_contract import AuditExportSpec
from ..application.export_submit_authorization import AuditExportSubmitAuthorizationRequest
from ..application.submit_export import AcceptedAuditExport,AuditExportSubmitError

_DATE=re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z',re.ASCII)
_REQUIRED={'purpose','start_at','end_at'}
_OPTIONAL={'action','outcome','actor_id','target_object_type','target_object_id','trace_id'}
def _pairs(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError('duplicate key')
        result[k]=v
    return result
def _constant(_):raise ValueError('nonstandard constant')
async def _body(request,headers):
    types=[v for k,v in headers if k.lower()==b'content-type']
    if len(types)!=1 or types[0].strip().lower() not in (b'application/json',b'application/json; charset=utf-8'):
        raise ApplicationError('REQUEST_MALFORMED')
    raw=bytearray()
    try:
        async for chunk in request.stream():
            if len(raw)+len(chunk)>8192:raise ApplicationError('REQUEST_MALFORMED')
            raw.extend(chunk)
        try:return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=_pairs,parse_constant=_constant)
        except (ValueError,TypeError,RecursionError):raise ApplicationError('REQUEST_MALFORMED') from None
    finally:raw[:]=b'\x00'*len(raw)
def _date(v):
    if type(v) is not str or _DATE.fullmatch(v) is None:raise ValueError('invalid date')
    return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)
def _ref(v):
    if v is None:return None
    if type(v) is not str:raise ValueError('invalid identifier')
    value=UUID(v)
    if not value.int or str(value)!=v:raise ValueError('noncanonical identifier')
    return value
def _spec(body,project_id):
    if type(body) is not dict or not _REQUIRED<=set(body) or set(body)-(_REQUIRED|_OPTIONAL):raise ApplicationError('REQUEST_MALFORMED')
    try:
        return AuditExportSpec('DEPLOYMENT' if project_id is None else 'PROJECT',project_id,body['purpose'],
            _date(body['start_at']),_date(body['end_at']),body.get('action'),body.get('outcome'),_ref(body.get('actor_id')),
            body.get('target_object_type'),_ref(body.get('target_object_id')),_ref(body.get('trace_id')))
    except (ValueError,TypeError,OverflowError):raise ApplicationError('AUDIT_EXPORT_SCOPE_INVALID') from None

def create_audit_export_submit_router(*,sessions,exports,origins):
    if any(v is None for v in (sessions,exports,origins)):raise ValueError('Current submit dependencies required')
    router=APIRouter()
    async def submit(request,project_id):
        headers=tuple(request.scope.get('headers',()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError('AUTH_CSRF_INVALID') from None
        token,csrf,key=_session_cookie(headers),_csrf_header(headers),_idempotency_header(headers)
        if request.url.query:raise ApplicationError('REQUEST_MALFORMED')
        if project_id is not None and not project_id.int:raise ApplicationError('RESOURCE_NOT_FOUND')
        try:await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
        except SessionError as exc:raise _session_failure(exc) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        spec=_spec(await _body(request,headers),project_id)
        command=AuditExportSubmitAuthorizationRequest(token,csrf,UUID(request.state.trace_id),spec)
        try:
            result=await run_in_threadpool(exports.submit_idempotent,command,idempotency_key=key)
            if type(result) is not AcceptedAuditExport:raise ValueError('Invalid acceptance')
            result.__post_init__()
            if result.intent.spec!=spec:raise ValueError('Acceptance mismatch')
        except AuditExportSubmitError as exc:
            code={'AUTH_ACCESS_DENIED':'RESOURCE_NOT_FOUND','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED','VALIDATION_FAILED':'VALIDATION_FAILED',
                'AUDIT_EXPORT_SCOPE_INVALID':'AUDIT_EXPORT_SCOPE_INVALID','CONFLICT_IDEMPOTENCY':'CONFLICT_IDEMPOTENCY'}.get(exc.code,'SYSTEM_UNAVAILABLE')
            raise ApplicationError(code) from None
        except Exception:raise ApplicationError('SYSTEM_UNAVAILABLE') from None
        url=f'/api/v1/projects/{project_id}/jobs/{result.job_id}' if project_id is not None else f'/api/v1/admin/jobs/{result.job_id}'
        return JSONResponse(dict(data=dict(export_id=str(result.intent.export_id),job_id=str(result.job_id),state='PENDING',status_url=url),
            trace_id=request.state.trace_id),status_code=202,headers={'Location':url,'Cache-Control':'no-store'})
    @router.post('/api/v1/projects/{project_id}/audit-exports')
    async def project_submit(project_id:UUID,request:Request):return await submit(request,project_id)
    @router.post('/api/v1/admin/audit-exports')
    async def deployment_submit(request:Request):return await submit(request,None)
    return router
