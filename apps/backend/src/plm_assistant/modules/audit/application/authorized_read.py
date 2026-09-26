"""Current licensed Session/role proof, safe scope projection, no HTTP/export."""
from dataclasses import dataclass,field,replace
from datetime import datetime,timezone
from uuid import UUID
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from ..domain.audit_event import AuditEventDraft,_uuid
from .queries.audit_query import (
    AuditQueryService,AuditSearch,AuditPosition,AuditEventView,AuditPage,AuditAccessDenied,AuditQueryError,
)


class AuthorizedAuditReadError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditListQuery:
    session_token: bytes = field(repr=False)
    project_id: UUID | None  # None explicitly means DEPLOYMENT, never fallback
    trace_id: UUID
    search: AuditSearch


@dataclass(frozen=True,slots=True)
class AuditGetQuery:
    session_token: bytes = field(repr=False)
    project_id: UUID | None
    trace_id: UUID
    event_id: UUID


@dataclass(frozen=True,slots=True)
class AuthorizedAuditListContext:
    """Actual read binding metadata, NOT reusable permission or cursor authority."""
    actor_id: UUID
    project_id: UUID | None
    page: AuditPage


class _BoundAccess:
    """Private same-tx capability created ONLY after actual current authz.

    It doesn't authenticate by a client-supplied UUID/boolean or survive UOWs.
    Existing low-level Query remains a trusted caller contract, not public auth.
    """
    def __init__(self,tx,principal,project):self.tx,self.principal,self.project=tx,principal,project
    def can_read_project(self,tx,principal,project):
        return tx is self.tx and principal is self.principal and self.project is not None and project==self.project
    def can_read_deployment(self,tx,principal):
        return tx is self.tx and principal is self.principal and self.project is None


def _aware(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


class AuthorizedAuditReadService:
    def __init__(self,*,unit_of_work,project_access,deployment_access,projects,license_guard,repository,clock=None):
        if any(v is None for v in (unit_of_work,project_access,deployment_access,projects,license_guard,repository)):
            raise ValueError("Audit read dependencies required")
        self._uow,self._project_access,self._deployment_access=unit_of_work,project_access,deployment_access
        self._projects,self._guard,self._repository=projects,license_guard,repository
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def list(self,query):
        return self._read(query,listing=True)

    def list_with_actor(self,query):
        return self._read(query,listing=True,include_actor=True)

    def get(self,query):
        return self._read(query,listing=False)

    def _read(self,q,*,listing,include_actor=False):
        if (type(q) is not (AuditListQuery if listing else AuditGetQuery)
                or type(q.session_token) is not bytes or len(q.session_token)!=32
                or not _uuid(q.trace_id) or not _uuid(q.project_id,optional=True)):
            raise AuthorizedAuditReadError("VALIDATION_FAILED")
        try:
            if listing:
                if type(q.search) is not AuditSearch:raise AuditQueryError("audit search is invalid")
                q.search.__post_init__()
                if q.search.after is not None:
                    if type(q.search.after) is not AuditPosition:raise AuditQueryError("audit position is invalid")
                    q.search.after.__post_init__()
            elif not _uuid(q.event_id):raise AuditQueryError("audit event is invalid")
        except ValueError:
            raise AuthorizedAuditReadError("VALIDATION_FAILED") from None
        try:
            self._guard.require_valid(trace_id=q.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _aware(now):raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
                if q.project_id is None:
                    actor=self._deployment_access.authorized_admin(tx,session_token=q.session_token,now=now)
                else:
                    actor=self._project_access.authenticated_user(tx,session_token=q.session_token,now=now)
                if not _uuid(actor):raise AuthorizedAuditReadError("AUTH_ACCESS_DENIED")
                if q.project_id is not None:
                    operation="AUDIT_PROJECT_LIST" if listing else "AUDIT_PROJECT_GET"
                    proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=q.project_id,operation=operation)
                    if (type(proof) is not AuthorizedProjectAction or proof.user_id!=actor or proof.project_id!=q.project_id
                            or proof.operation!=operation or proof.project_role!="PROJECT_MANAGER"):
                        raise AuthorizedAuditReadError("RESOURCE_NOT_FOUND")
                principal=object()
                reader=AuditQueryService(access=_BoundAccess(tx,principal,q.project_id),repository=self._repository)
                if listing:
                    page=reader.list_deployment(tx,principal,q.search) if q.project_id is None else reader.list_project(tx,principal,q.project_id,q.search)
                    page=self._page(page,q.project_id,q.search)
                    return AuthorizedAuditListContext(actor,q.project_id,page) if include_actor else page
                view=reader.get_deployment(tx,principal,q.event_id) if q.project_id is None else reader.get_project(tx,principal,q.project_id,q.event_id)
                if view is None:raise AuthorizedAuditReadError("RESOURCE_NOT_FOUND")
                view=self._view(view,q.project_id)
                if view.audit_event_id!=q.event_id:raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
                return view
        except AuthorizedAuditReadError:raise
        except (ProjectAuthorizationError,AuditAccessDenied):
            raise AuthorizedAuditReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AuthorizedAuditReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE") from None

    @staticmethod
    def _view(view,project):
        if (type(view) is not AuditEventView or not _uuid(view.audit_event_id) or not _aware(view.occurred_at)
                or view.event_scope!=("DEPLOYMENT" if project is None else "PROJECT") or view.target_project_id!=project):
            raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
        # Reuse owned safe codes/actor/ref validation, never copy raw ORM fields
        # or actor_hint_digest into the projection.
        AuditEventDraft(trace_id=view.trace_id,event_scope=view.event_scope,target_project_id=view.target_project_id,
            actor_type=view.actor_type,actor_id=view.actor_id,original_actor_id=view.original_actor_id,actor_hint_digest=None,
            action=view.action,outcome=view.outcome,target_owner_module=view.target_owner_module,
            target_object_type=view.target_object_type,target_object_id=view.target_object_id,target_version_id=view.target_version_id,
            reason_code=view.reason_code,before_state=view.before_state,after_state=view.after_state)
        return replace(view,occurred_at=view.occurred_at.astimezone(timezone.utc))

    def _page(self,page,project,search):
        if (type(page) is not AuditPage or type(page.items) is not tuple or len(page.items)>search.page_size
                or type(page.has_more) is not bool):raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
        items=tuple(self._view(view,project) for view in page.items)
        positions=[(v.occurred_at,v.audit_event_id) for v in items]
        if (len(set(v.audit_event_id for v in items))!=len(items)
                or any(a<=b for a,b in zip(positions,positions[1:]))
                or any(not search.start_at<=v.occurred_at<search.end_at for v in items)
                or any(getattr(v,name)!=value for v in items for name,value in (
                    ("action",search.action),("outcome",search.outcome),("actor_id",search.actor_id),
                    ("target_object_type",search.target_object_type),("target_object_id",search.target_object_id),
                    ("trace_id",search.trace_id)) if value is not None)
                or search.after is not None and any(p>=(search.after.occurred_at,search.after.audit_event_id) for p in positions)):
            raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
        next_position=None
        if page.has_more:
            if len(items)!=search.page_size or type(page.next_position) is not AuditPosition:
                raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
            page.next_position.__post_init__()
            last=items[-1]
            if (page.next_position.occurred_at,page.next_position.audit_event_id)!=(last.occurred_at,last.audit_event_id):
                raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
            next_position=AuditPosition(last.occurred_at,last.audit_event_id)
        elif page.next_position is not None:raise AuthorizedAuditReadError("AUDIT_UNAVAILABLE")
        return AuditPage(items,next_position,page.has_more)
