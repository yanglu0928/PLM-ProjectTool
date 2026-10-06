"""Authorized visibility-filtered Survey Assignment reads."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError, ProjectAuthorizationService,
)

from .assignment_views import SurveyAssignmentPage, SurveyAssignmentView


class SurveyAssignmentReadError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ASSIGNMENT_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyAssignmentReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    survey_round_id: uuid.UUID


class SurveyAssignmentReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: object,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Survey Assignment read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_assignments(
        self, query: SurveyAssignmentReadQuery, *, page_size: int,
        after_created_at: datetime | None = None,
        after_assignment_id: uuid.UUID | None = None,
    ) -> SurveyAssignmentPage:
        self._validate(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (after_created_at is None) != (after_assignment_id is None)
                or after_created_at is not None and (
                    type(after_created_at) is not datetime
                    or after_created_at.tzinfo is None
                    or after_created_at.utcoffset() is None
                    or type(after_assignment_id) is not uuid.UUID
                    or after_assignment_id.int == 0)):
            raise SurveyAssignmentReadError("VALIDATION_FAILED")

        def read(tx, actor, role):
            rows = self._repository.list_assignments(
                tx, project_id=query.project_id,
                survey_round_id=query.survey_round_id, actor_id=actor,
                actor_role=role, after_created_at=after_created_at,
                after_assignment_id=after_assignment_id, limit=page_size + 1,
            )
            if (type(rows) is not tuple or len(rows) > page_size + 1
                    or any(type(row) is not SurveyAssignmentView for row in rows)):
                raise SurveyAssignmentReadError()
            items, more = rows[:page_size], len(rows) > page_size
            tail = items[-1] if more else None
            return SurveyAssignmentPage(
                items, None if tail is None else tail.created_at,
                None if tail is None else tail.survey_assignment_id, more,
            )
        return self._run(query, "SURVEY_ASSIGNMENT_LIST", read)

    def get_assignment(
        self, query: SurveyAssignmentReadQuery,
        survey_assignment_id: uuid.UUID,
    ) -> SurveyAssignmentView:
        self._validate(query)
        if type(survey_assignment_id) is not uuid.UUID or survey_assignment_id.int == 0:
            raise SurveyAssignmentReadError("VALIDATION_FAILED")

        def read(tx, actor, role):
            result = self._repository.get_assignment(
                tx, project_id=query.project_id,
                survey_round_id=query.survey_round_id,
                survey_assignment_id=survey_assignment_id,
                actor_id=actor, actor_role=role,
            )
            if type(result) is not SurveyAssignmentView:
                raise SurveyAssignmentReadError("RESOURCE_NOT_FOUND")
            return result
        return self._run(query, "SURVEY_ASSIGNMENT_GET", read)

    def _run(self, query, operation, read):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise SurveyAssignmentReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveyAssignmentReadError("AUTH_ACCESS_DENIED")
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                if (type(authorized) is not AuthorizedProjectAction
                        or authorized.user_id != actor
                        or authorized.project_id != query.project_id
                        or authorized.operation != operation):
                    raise SurveyAssignmentReadError("RESOURCE_NOT_FOUND")
                return read(tx, actor, authorized.project_role)
        except SurveyAssignmentReadError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyAssignmentReadError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyAssignmentReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SurveyAssignmentReadError() from None

    @staticmethod
    def _validate(query: SurveyAssignmentReadQuery) -> None:
        if (type(query) is not SurveyAssignmentReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    query.trace_id, query.project_id, query.survey_round_id))):
            raise SurveyAssignmentReadError("VALIDATION_FAILED")
