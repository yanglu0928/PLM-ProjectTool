"""Frozen creator-or-PM cancellation policy; Root coordinates must be Owner-bound."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID
from .export_contract import AuditExportSpec
from .export_submit_authorization import AuditExportSubmitAuthorizationError as Error
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError,ALL_MEMBERS
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


@dataclass(frozen=True,slots=True)
class AuditExportCancelAuthorizationRequest:
    session_token: bytes=field(repr=False)
    csrf_token: bytes=field(repr=False)
    trace_id: UUID
    spec: AuditExportSpec
    original_actor_id: UUID  # Trusted Owner reads immutable Root; NEVER client assertion.


@dataclass(frozen=True,slots=True)
class AuthorizedAuditExportCancel:
    actor_id: UUID
    scope: str
    project_id: UUID|None
    original_actor_id: UUID
    intent_hash: str


class AuditExportCancelAuthorization:
    def __init__(self,*,project_access,deployment_access,projects,license_guard,clock=None):
        if any(v is None for v in (project_access,deployment_access,projects,license_guard)):
            raise ValueError('Current cancellation authority required')
        self._project,self._deployment,self._projects,self._guard=project_access,deployment_access,projects,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def require_in_transaction(self,tx,*,request):
        if (type(request) is not AuditExportCancelAuthorizationRequest
                or any(type(v) is not bytes or len(v)!=32 for v in (request.session_token,request.csrf_token))
                or any(type(v) is not UUID or not v.int for v in (request.trace_id,request.original_actor_id))
                or type(request.spec) is not AuditExportSpec):raise Error('VALIDATION_FAILED')
        try:fingerprint=request.spec.fingerprint()
        except ValueError:raise Error('AUDIT_EXPORT_SCOPE_INVALID') from None
        try:
            self._guard.require_valid(trace_id=request.trace_id)
            now=self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:raise Error('AUDIT_UNAVAILABLE')
            if request.spec.scope=='DEPLOYMENT':
                actor=self._deployment.authorized_admin(tx,session_token=request.session_token,csrf_token=request.csrf_token,now=now)
            else:
                actor=self._project.authenticated_user(tx,session_token=request.session_token,csrf_token=request.csrf_token,now=now)
            if type(actor) is not UUID or not actor.int:raise Error('AUTH_ACCESS_DENIED')
            if request.spec.scope=='PROJECT':
                proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=request.spec.project_id,operation='AUDIT_PROJECT_CANCEL')
                if (type(proof) is not AuthorizedProjectAction or proof.user_id!=actor
                        or proof.project_id!=request.spec.project_id or proof.operation!='AUDIT_PROJECT_CANCEL'
                        or proof.project_role not in ALL_MEMBERS
                        or actor!=request.original_actor_id and proof.project_role!='PROJECT_MANAGER'):
                    raise Error('RESOURCE_NOT_FOUND')
            if request.spec.fingerprint()!=fingerprint:raise Error('AUDIT_UNAVAILABLE')
            return AuthorizedAuditExportCancel(actor,request.spec.scope,request.spec.project_id,request.original_actor_id,fingerprint)
        except Error:raise
        except ProjectAuthorizationError:raise Error('RESOURCE_NOT_FOUND') from None
        except RuntimeLicenseError:raise Error('LICENSE_OPERATION_DENIED') from None
        except Exception:raise Error('AUDIT_UNAVAILABLE') from None
