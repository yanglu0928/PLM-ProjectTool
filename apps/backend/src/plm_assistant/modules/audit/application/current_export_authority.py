"""Recheck current async authority; Owner must bind persistent export and lease first."""
from plm_assistant.modules.auth.application.current_user import CurrentUserFacts, CurrentUserAccessPort
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction, ProjectAuthorizationError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from .export_contract import AuditExportAuthorityRequest


class AuditExportCurrentAuthorityError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class AuditExportCurrentAuthority:
    def __init__(self, *, users: CurrentUserAccessPort, projects, license_guard):
        if any(value is None for value in (users, projects, license_guard)):
            raise ValueError("current export authority dependencies required")
        self._users, self._projects, self._guard = users, projects, license_guard

    def assert_current(self, transaction: object, *, request: AuditExportAuthorityRequest) -> None:
        if type(request) is not AuditExportAuthorityRequest:
            raise AuditExportCurrentAuthorityError("VALIDATION_FAILED")
        try:
            request.__post_init__()
        except ValueError:
            raise AuditExportCurrentAuthorityError("VALIDATION_FAILED") from None
        try:
            self._guard.require_valid(trace_id=request.export_id)
            facts = self._users.current_enabled_user(transaction, user_id=request.actor_id)
            if type(facts) is not CurrentUserFacts or facts.user_id != request.actor_id:
                raise AuditExportCurrentAuthorityError("AUTH_ACCESS_DENIED")
            facts.__post_init__()
            if request.scope == "DEPLOYMENT":
                if facts.deployment_role != "DEPLOYMENT_ADMIN":
                    raise AuditExportCurrentAuthorityError("AUTH_ACCESS_DENIED")
            else:
                proof = self._projects.require_in_transaction(transaction, user_id=request.actor_id,
                    project_id=request.project_id, operation="AUDIT_PROJECT_EXPORT")
                if (type(proof) is not AuthorizedProjectAction or proof.user_id != request.actor_id
                        or proof.project_id != request.project_id or proof.operation != "AUDIT_PROJECT_EXPORT"
                        or proof.project_role != "PROJECT_MANAGER"):
                    raise AuditExportCurrentAuthorityError("RESOURCE_NOT_FOUND")
        except AuditExportCurrentAuthorityError:
            raise
        except RuntimeLicenseError:
            raise AuditExportCurrentAuthorityError("LICENSE_OPERATION_DENIED") from None
        except ProjectAuthorizationError:
            raise AuditExportCurrentAuthorityError("RESOURCE_NOT_FOUND") from None
        except Exception:
            raise AuditExportCurrentAuthorityError("AUDIT_UNAVAILABLE") from None
