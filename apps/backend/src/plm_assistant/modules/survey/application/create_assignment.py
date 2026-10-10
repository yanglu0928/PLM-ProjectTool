"""Authorized atomic creation of Survey Assignments."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)

from .assignment_views import SurveyAssignmentView


_OPERATION = "V1_SURVEY_ASSIGNMENT_CREATE"


class SurveyAssignmentCreateError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ASSIGNMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSurveyAssignment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID
    department_id: uuid.UUID
    assignee_user_id: uuid.UUID | None
    idempotency_key: str = field(repr=False)


class SurveyAssignmentCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: object, receipts: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization,
                repository, receipts, audit)):
            raise ValueError("Survey Assignment create dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSurveyAssignment) -> SurveyAssignmentView:
        self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "survey_round_id": str(command.survey_round_id),
                "department_id": str(command.department_id),
                "assignee_user_id": (
                    None if command.assignee_user_id is None
                    else str(command.assignee_user_id)
                ),
            })
            assignment_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="SURVEY_ASSIGNMENT_CREATE",
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != command.project_id
                        or authorized.operation != "SURVEY_ASSIGNMENT_CREATE"
                        or authorized.project_role not in (
                            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER")):
                    raise SurveyAssignmentCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 201:
                        raise SurveyAssignmentCreateError()
                    result = self._repository.get_initial(
                        tx, project_id=command.project_id,
                        survey_assignment_id=replay.ref_id, actor_id=actor,
                    )
                    if not self._matches(result, command, replay.ref_id):
                        raise SurveyAssignmentCreateError()
                    return result
                result = self._repository.create(
                    tx, survey_assignment_id=assignment_id,
                    project_id=command.project_id,
                    survey_round_id=command.survey_round_id,
                    department_id=command.department_id,
                    assignee_user_id=command.assignee_user_id, actor_id=actor,
                )
                if not self._matches(result, command, assignment_id):
                    raise SurveyAssignmentCreateError()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="SURVEY_ASSIGNMENT_CREATED", outcome="SUCCESS",
                    target_owner_module="survey", target_object_type="SRV-04",
                    target_object_id=assignment_id,
                    target_version_id=result.survey_version_id,
                    after_state="ASSIGNED",
                ))
                if type(audit_id) is not uuid.UUID or audit_id.int == 0:
                    raise SurveyAssignmentCreateError()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, assignment_id, 201,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except SurveyAssignmentCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyAssignmentCreateError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyAssignmentCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise SurveyAssignmentCreateError(error.code) from None
        except Exception:
            raise SurveyAssignmentCreateError() from None

    def _actor(self, tx: object, command: CreateSurveyAssignment) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise SurveyAssignmentCreateError()
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SurveyAssignmentCreateError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _validate(command: CreateSurveyAssignment) -> None:
        if (type(command) is not CreateSurveyAssignment
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.trace_id, command.project_id, command.survey_round_id,
                    command.department_id,
                ))
                or command.assignee_user_id is not None and (
                    type(command.assignee_user_id) is not uuid.UUID
                    or command.assignee_user_id.int == 0)):
            raise SurveyAssignmentCreateError("VALIDATION_FAILED")

    @staticmethod
    def _matches(view: object, command: CreateSurveyAssignment,
                 assignment_id: uuid.UUID) -> bool:
        return (type(view) is SurveyAssignmentView
                and view.survey_assignment_id == assignment_id
                and view.project_id == command.project_id
                and view.survey_round_id == command.survey_round_id
                and view.department_id == command.department_id
                and view.assignee_user_id == command.assignee_user_id
                and view.submission_state == "ASSIGNED" and view.etag == '"v0"'
                and view.response_count == 0)
