"""Real current submit authority in caller UOW; no enqueue/commit/receipt."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from .export_contract import AuditExportSpec


class AuditExportSubmitAuthorizationError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditExportSubmitAuthorizationRequest:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: UUID
    spec: AuditExportSpec


@dataclass(frozen=True,slots=True)
class AuthorizedAuditExportSubmit:
    """Binding metadata ONLY; cannot replace new transaction authorization."""
    actor_id: UUID
    scope: str
    project_id: UUID|None
    intent_hash: str


class AuditExportSubmitAuthorization:
    def __init__(self,*,project_access,deployment_access,projects,license_guard,clock=None):
        if any(value is None for value in (project_access,deployment_access,projects,license_guard)):
            raise ValueError("Audit export authorization dependencies required")
        self._project_access,self._deployment_access=project_access,deployment_access
        self._projects,self._guard=projects,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def require_in_transaction(self,tx,*,request):
        if (type(request) is not AuditExportSubmitAuthorizationRequest
                or type(request.session_token) is not bytes or len(request.session_token)!=32
                or type(request.csrf_token) is not bytes or len(request.csrf_token)!=32
                or type(request.trace_id) is not UUID or not request.trace_id.int
                or type(request.spec) is not AuditExportSpec):
            raise AuditExportSubmitAuthorizationError("VALIDATION_FAILED")
        try:
            fingerprint=request.spec.fingerprint()
        except ValueError:
            raise AuditExportSubmitAuthorizationError("AUDIT_EXPORT_SCOPE_INVALID") from None
        try:
            # Even deployment-admin recovery Auth adapter grants no License exemption.
            self._guard.require_valid(trace_id=request.trace_id)
            now=self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise AuditExportSubmitAuthorizationError("AUDIT_UNAVAILABLE")
            if request.spec.scope=="DEPLOYMENT":
                actor=self._deployment_access.authorized_admin(tx,session_token=request.session_token,csrf_token=request.csrf_token,now=now)
            else:
                actor=self._project_access.authenticated_user(tx,session_token=request.session_token,csrf_token=request.csrf_token,now=now)
            if type(actor) is not UUID or not actor.int:
                raise AuditExportSubmitAuthorizationError("AUTH_ACCESS_DENIED")
            if request.spec.scope=="PROJECT":
                proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=request.spec.project_id,operation="AUDIT_PROJECT_EXPORT")
                if (type(proof) is not AuthorizedProjectAction or proof.user_id!=actor
                        or proof.project_id!=request.spec.project_id or proof.operation!="AUDIT_PROJECT_EXPORT"
                        or proof.project_role!="PROJECT_MANAGER"):
                    raise AuditExportSubmitAuthorizationError("RESOURCE_NOT_FOUND")
            if request.spec.fingerprint()!=fingerprint:
                raise AuditExportSubmitAuthorizationError("AUDIT_UNAVAILABLE")
            return AuthorizedAuditExportSubmit(actor,request.spec.scope,request.spec.project_id,fingerprint)
        except AuditExportSubmitAuthorizationError:raise
        except ProjectAuthorizationError:
            raise AuditExportSubmitAuthorizationError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise AuditExportSubmitAuthorizationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise AuditExportSubmitAuthorizationError("AUDIT_UNAVAILABLE") from None
