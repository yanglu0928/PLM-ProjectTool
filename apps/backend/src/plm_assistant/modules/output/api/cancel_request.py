"""Opt-in OUTPUT_REQUEST_CANCEL HTTP adapter; never mounted by default."""
from __future__ import annotations
import json,uuid
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import (
    _csrf_header,_idempotency_header,_session_cookie,_session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError,SessionService
from plm_assistant.modules.output.application.cancel_request import (
    CancelOutputRequest,OutputRequestCancelError,OutputRequestCancelResult,
)
from plm_assistant.modules.platform.api.error_handlers import ApplicationError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.api.create_project import _canonical_uuid,_read_json
_ERROR_MAP={
    "AUTH_ACCESS_DENIED":"RESOURCE_NOT_FOUND","RESOURCE_NOT_FOUND":"RESOURCE_NOT_FOUND",
    "CONFLICT_VERSION":"CONFLICT_VERSION","CONFLICT_IDEMPOTENCY":"CONFLICT_IDEMPOTENCY",
    "CONFLICT_STATE":"CONFLICT_STATE","LICENSE_OPERATION_DENIED":"LICENSE_OPERATION_DENIED",
    "VALIDATION_FAILED":"VALIDATION_FAILED","SYSTEM_UNAVAILABLE":"SYSTEM_UNAVAILABLE",
}
def create_output_request_cancel_router(*,sessions,origins,service):
    if any(v is None for v in (sessions,origins,service)):
        raise ValueError("Output cancel HTTP dependencies are required")
    router=APIRouter()
    @router.post("/api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel")
    async def cancel(project_id:uuid.UUID,output_request_id:uuid.UUID,request:Request):
        headers=tuple(request.scope.get("headers",()))
        try:origins.require_trusted(headers)
        except LoginOriginError:raise ApplicationError("AUTH_CSRF_INVALID") from None
        token,csrf,key=_session_cookie(headers),_csrf_header(headers),_idempotency_header(headers)
        version=parse_if_match(headers)
        if request.url.query:raise ApplicationError("REQUEST_MALFORMED")
        if not project_id.int or not output_request_id.int:raise ApplicationError("RESOURCE_NOT_FOUND")
        try:await run_in_threadpool(sessions.validate,token,csrf_token=csrf,require_csrf=True)
        except SessionError as exc:raise _session_failure(exc) from None
        except Exception:raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        body=await _read_json(request,headers)
        if type(body) is not dict or set(body)!={"reason"}:
            raise ApplicationError("REQUEST_MALFORMED")
        trace_id=_canonical_uuid(request.state.trace_id)
        command=CancelOutputRequest(token,csrf,trace_id,project_id,output_request_id,
                                    body["reason"],version)
        try:
            result=await run_in_threadpool(service.cancel,command,idempotency_key=key)
        except OutputRequestCancelError as exc:
            raise ApplicationError(_ERROR_MAP.get(exc.code,"SYSTEM_UNAVAILABLE")) from None
        except IdempotencyError:
            raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
        except Exception:raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not OutputRequestCancelResult
                or result.output_request_id!=output_request_id or result.project_id!=project_id
                or result.state not in {"CANCEL_REQUESTED","CANCELLED","SUCCEEDED","FAILED"}
                or type(result.changed) is not bool or type(result.lock_version) is not int
                or result.lock_version<0 or result.status_code!=200):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag=f'"v{result.lock_version}"'
        return JSONResponse({"data":{"output_request_id":str(output_request_id),
            "state":result.state,"changed":result.changed,"etag":etag},
            "trace_id":request.state.trace_id},
            headers={"ETag":etag,"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
    return router
