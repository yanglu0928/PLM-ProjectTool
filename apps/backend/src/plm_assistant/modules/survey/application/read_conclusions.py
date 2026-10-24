"""Authorized SurveyConclusion version list and detail reads."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

from .conclusion_views import (
    SurveyConclusionPage, SurveyConclusionSummaryView, SurveyConclusionView,
)


class SurveyConclusionReadError(RuntimeError):
    def __init__(self, code: str = "SURVEY_CONCLUSION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyConclusionReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


class SurveyConclusionReadService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: object, clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Survey Conclusion read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_conclusions(
        self, query: SurveyConclusionReadQuery, *, page_size: int,
        after_created_at: datetime | None = None,
        after_conclusion_id: uuid.UUID | None = None,
    ) -> SurveyConclusionPage:
        self._validate_query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (after_created_at is None) != (after_conclusion_id is None)
                or after_created_at is not None and (
                    type(after_created_at) is not datetime
                    or after_created_at.tzinfo is None
                    or after_created_at.utcoffset() is None
                    or type(after_conclusion_id) is not uuid.UUID
                    or after_conclusion_id.int == 0)):
            raise SurveyConclusionReadError("VALIDATION_FAILED")

        def read(tx: object) -> SurveyConclusionPage:
            rows = self._repository.list_conclusions(
                tx, project_id=query.project_id,
                after_created_at=after_created_at,
                after_conclusion_id=after_conclusion_id,
                limit=page_size + 1,
            )
            if (type(rows) is not tuple or len(rows) > page_size + 1
                    or any(type(row) is not SurveyConclusionSummaryView
                           for row in rows)):
                raise SurveyConclusionReadError()
            items, more = rows[:page_size], len(rows) > page_size
            tail = items[-1] if more else None
            return SurveyConclusionPage(
                items, None if tail is None else tail.created_at,
                None if tail is None else tail.survey_conclusion_id, more,
            )

        return self._run(query, "SURVEY_CONCLUSION_LIST", read)

    def get_conclusion(
        self, query: SurveyConclusionReadQuery,
        survey_conclusion_id: uuid.UUID,
    ) -> SurveyConclusionView:
        self._validate_query(query)
        if (type(survey_conclusion_id) is not uuid.UUID
                or survey_conclusion_id.int == 0):
            raise SurveyConclusionReadError("VALIDATION_FAILED")

        def read(tx: object) -> SurveyConclusionView:
            result = self._repository.get_conclusion(
                tx, project_id=query.project_id,
                survey_conclusion_id=survey_conclusion_id,
            )
            if type(result) is not SurveyConclusionView:
                raise SurveyConclusionReadError("RESOURCE_NOT_FOUND")
            return result

        return self._run(query, "SURVEY_CONCLUSION_GET", read)

    def _run(self, query, operation: str, read: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise SurveyConclusionReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveyConclusionReadError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                return read(tx)
        except SurveyConclusionReadError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyConclusionReadError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyConclusionReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SurveyConclusionReadError() from None

    @staticmethod
    def _validate_query(query: SurveyConclusionReadQuery) -> None:
        if (type(query) is not SurveyConclusionReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID
                or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID
                or query.project_id.int == 0):
            raise SurveyConclusionReadError("VALIDATION_FAILED")
