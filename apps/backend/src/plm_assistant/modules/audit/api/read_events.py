"""Opt-in licensed, scope-isolated Audit GET; no export or writes."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import re
from uuid import UUID
from fastapi import APIRouter,Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_read import AuthorizedAuditReadService,AuthorizedAuditReadError,AuthorizedAuditListContext,AuditListQuery,AuditGetQuery
from ..application.queries.audit_query import AuditSearch,AuditPage
from .list_cursor import AuditListCursorCodec
from .search_resolver import AuditCursorSearchResolver

_FIELDS={"start_at","end_at","page_size","cursor","action","outcome","actor_id","target_object_type","target_object_id","trace_id"}
_DATE=re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z",re.ASCII)
_SIZE=re.compile(r"[1-9][0-9]{0,2}\Z",re.ASCII)


def _date(raw):
    if _DATE.fullmatch(raw) is None:raise ValueError()
    return datetime.fromisoformat(raw.replace("Z","+00:00")).astimezone(timezone.utc)


def _search(request,clock):
    entries=list(request.query_params.multi_items())
    if len(entries)>len(_FIELDS) or len(set(k for k,_ in entries))!=len(entries) or any(k not in _FIELDS for k,_ in entries):
        raise ApplicationError("REQUEST_MALFORMED")
    p=dict(entries)
    try:
        size=p.get("page_size","50")
        if _SIZE.fullmatch(size) is None:raise ValueError()
        if ("start_at" in p)!=("end_at" in p):raise ValueError()
        omitted="start_at" not in p
        if omitted:
            end=clock()
            if type(end) is not datetime or end.tzinfo is None or end.utcoffset() is None:
                raise ApplicationError("SYSTEM_UNAVAILABLE")
            end=end.astimezone(timezone.utc);start=end-timedelta(days=1)
        else:start,end=_date(p["start_at"]),_date(p["end_at"])
        search=AuditSearch(start,end,page_size=int(size),action=p.get("action"),outcome=p.get("outcome"),
            actor_id=UUID(p["actor_id"]) if "actor_id" in p else None,target_object_type=p.get("target_object_type"),
            target_object_id=UUID(p["target_object_id"]) if "target_object_id" in p else None,
            trace_id=UUID(p["trace_id"]) if "trace_id" in p else None)
        return search,p.get("cursor"),omitted
    except (ValueError,TypeError,OverflowError):raise ApplicationError("VALIDATION_FAILED") from None


def _public(view,project):
    try:view=AuthorizedAuditReadService._view(view,project)
    except Exception:raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    ref=lambda value:str(value) if value is not None else None
    return dict(audit_event_id=str(view.audit_event_id),occurred_at=view.occurred_at.isoformat().replace("+00:00","Z"),
        event_scope=view.event_scope,project_id=ref(view.target_project_id),
        actor=dict(type=view.actor_type,user_id=ref(view.actor_id),original_user_id=ref(view.original_actor_id)),
        action=view.action,outcome=view.outcome,
        target=dict(owner_module=view.target_owner_module,object_type=view.target_object_type,object_id=ref(view.target_object_id),version_id=ref(view.target_version_id)),
        summary=dict(reason_code=view.reason_code,before_state=view.before_state,after_state=view.after_state),trace_id=str(view.trace_id))


def _error(exc):
    code={"AUTH_ACCESS_DENIED":"AUTH_SESSION_EXPIRED","RESOURCE_NOT_FOUND":"RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED":"VALIDATION_FAILED","REQUEST_MALFORMED":"REQUEST_MALFORMED",
        "LICENSE_OPERATION_DENIED":"LICENSE_OPERATION_DENIED"}.get(exc.code,"SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_audit_read_router(*,reads,origins,cursors,clock=None):
    if reads is None or origins is None or type(cursors) is not AuditListCursorCodec:
        raise ValueError("Audit reads, origins and dedicated cursors required")
    clock=clock or (lambda:datetime.now(timezone.utc))
    router=APIRouter()

    def token(request):
        headers=tuple(request.scope.get("headers",()))
        try:origins.require_trusted_host(headers)
        except LoginOriginError:raise ApplicationError("AUTH_CSRF_INVALID") from None
        return _session_cookie(headers)

    async def listing(request,project):
        session=token(request)
        if project is not None and project.int==0:raise ApplicationError("RESOURCE_NOT_FOUND")
        search,cursor,omitted=_search(request,clock)
        try:
            context=await run_in_threadpool(reads.list_resolved,AuditListQuery(session,project,UUID(request.state.trace_id),search),
                AuditCursorSearchResolver(cursors,cursor,dates_omitted=omitted))
            if (type(context) is not AuthorizedAuditListContext or context.project_id!=project
                    or type(context.actor_id) is not UUID or context.actor_id.int==0 or type(context.search) is not AuditSearch
                    or type(context.page) is not AuditPage):raise ValueError()
            page=AuthorizedAuditReadService._page(context.page,project,context.search)
            next_cursor=cursors.encode(session_token=session,actor_id=context.actor_id,project_id=project,
                search=replace(context.search,after=None),position=page.next_position) if page.has_more else None
            data=dict(items=[_public(v,project) for v in page.items],next_cursor=next_cursor,has_more=page.has_more)
        except AuthorizedAuditReadError as exc:raise _error(exc) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(dict(data=data,trace_id=request.state.trace_id),headers={"Cache-Control":"no-store"})

    async def detail(request,project,event):
        session=token(request)
        if request.url.query:raise ApplicationError("REQUEST_MALFORMED")
        if event.int==0 or project is not None and project.int==0:raise ApplicationError("RESOURCE_NOT_FOUND")
        try:
            view=await run_in_threadpool(reads.get,AuditGetQuery(session,project,UUID(request.state.trace_id),event))
            if view.audit_event_id!=event:raise ValueError()
            data=_public(view,project)
        except AuthorizedAuditReadError as exc:raise _error(exc) from None
        except ApplicationError:raise
        except Exception:raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(dict(data=data,trace_id=request.state.trace_id),headers={"Cache-Control":"no-store"})

    @router.get("/api/v1/projects/{project_id}/audit-events")
    async def project_list(project_id:UUID,request:Request):return await listing(request,project_id)

    @router.get("/api/v1/projects/{project_id}/audit-events/{audit_event_id}")
    async def project_get(project_id:UUID,audit_event_id:UUID,request:Request):return await detail(request,project_id,audit_event_id)

    @router.get("/api/v1/admin/audit-events")
    async def admin_list(request:Request):return await listing(request,None)

    @router.get("/api/v1/admin/audit-events/{audit_event_id}")
    async def admin_get(audit_event_id:UUID,request:Request):return await detail(request,None,audit_event_id)

    return router
