"""Current original-user authority for asynchronous Parser preparation/publication."""

from __future__ import annotations

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobRequest, validate_parse_read_request,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)


class ParserAuthorityError(RuntimeError):
    def __init__(self, code: str = "PARSER_AUTHORITY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class ParserCurrentAuthority:
    def __init__(self, *, users, projects, license_guard):
        if any(value is None for value in (users, projects, license_guard)):
            raise ValueError("Current Parser authority dependencies required")
        self._users, self._projects, self._license = users, projects, license_guard

    def assert_current(self, tx, *, request: ParseJobRequest) -> None:
        if type(request) is not ParseJobRequest:
            raise ParserAuthorityError("VALIDATION_FAILED")
        try:
            validate_parse_read_request(request)
            self._license.require_valid(trace_id=request.trace_id)
            facts = self._users.current_enabled_user(tx, user_id=request.actor_id)
            if type(facts) is not CurrentUserFacts or facts.user_id != request.actor_id:
                raise ParserAuthorityError("AUTH_ACCESS_DENIED")
            facts.__post_init__()
            if request.scope == "GLOBAL":
                if facts.deployment_role != "DEPLOYMENT_ADMIN":
                    raise ParserAuthorityError("AUTH_ACCESS_DENIED")
                return
            proof = self._projects.require_in_transaction(tx,
                user_id=request.actor_id, project_id=request.project_id,
                operation="DOCUMENT_PARSE_PROCESS")
            if (type(proof) is not AuthorizedProjectAction
                    or proof.user_id != request.actor_id
                    or proof.project_id != request.project_id
                    or proof.operation != "DOCUMENT_PARSE_PROCESS"
                    or proof.project_role not in {
                        "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"}):
                raise ParserAuthorityError("RESOURCE_NOT_FOUND")
        except ParserAuthorityError:
            raise
        except RuntimeLicenseError:
            raise ParserAuthorityError("LICENSE_OPERATION_DENIED") from None
        except ProjectAuthorizationError as exc:
            raise ParserAuthorityError(
                "PROJECT_ARCHIVED" if exc.code == "PROJECT_ARCHIVED"
                else "RESOURCE_NOT_FOUND") from None
        except Exception:
            raise ParserAuthorityError() from None
