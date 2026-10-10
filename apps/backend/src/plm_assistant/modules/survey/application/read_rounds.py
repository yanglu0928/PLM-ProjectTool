"""Authorized Survey Round list and detail reads."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)

from .round_views import SurveyRoundPage, SurveyRoundView


class SurveyRoundReadError(RuntimeError):
    def __init__(self, code: str = "SURVEY_ROUND_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyRoundReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


class RepositoryPort(Protocol):
    def list_rounds(
        self, transaction: object, *, project_id: uuid.UUID,
        after_created_at: datetime | None, after_round_id: uuid.UUID | None,
        limit: int,
    ) -> tuple[SurveyRoundView, ...]: ...

    def get_round(
        self, transaction: object, *, project_id: uuid.UUID,
        survey_round_id: uuid.UUID,
    ) -> SurveyRoundView | None: ...


class SurveyRoundReadService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: object,
        license_guard: object, authorization: ProjectAuthorizationService,
        repository: RepositoryPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Survey Round read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_rounds(
        self, query: SurveyRoundReadQuery, *, page_size: int,
        after_created_at: datetime | None = None,
        after_round_id: uuid.UUID | None = None,
    ) -> SurveyRoundPage:
        self._validate_query(query)
        if (type(page_size) is not int or not 1 <= page_size <= 200
                or (after_created_at is None) != (after_round_id is None)
                or after_created_at is not None and (
                    type(after_created_at) is not datetime
                    or after_created_at.tzinfo is None
                    or after_created_at.utcoffset() is None
                    or type(after_round_id) is not uuid.UUID
                    or after_round_id.int == 0
                )):
            raise SurveyRoundReadError("VALIDATION_FAILED")

        def read(tx: object) -> SurveyRoundPage:
            rows = self._repository.list_rounds(
                tx, project_id=query.project_id,
                after_created_at=after_created_at,
                after_round_id=after_round_id, limit=page_size + 1,
            )
            if (type(rows) is not tuple or len(rows) > page_size + 1
                    or any(type(row) is not SurveyRoundView for row in rows)):
                raise SurveyRoundReadError()
            items, more = rows[:page_size], len(rows) > page_size
            tail = items[-1] if more else None
            return SurveyRoundPage(
                items=items,
                next_created_at=None if tail is None else tail.created_at,
                next_round_id=None if tail is None else tail.survey_round_id,
                has_more=more,
            )

        return self._run(query, "SURVEY_ROUND_LIST", read)

    def get_round(
        self, query: SurveyRoundReadQuery, survey_round_id: uuid.UUID,
    ) -> SurveyRoundView:
        self._validate_query(query)
        if type(survey_round_id) is not uuid.UUID or survey_round_id.int == 0:
            raise SurveyRoundReadError("VALIDATION_FAILED")

        def read(tx: object) -> SurveyRoundView:
            row = self._repository.get_round(
                tx, project_id=query.project_id,
                survey_round_id=survey_round_id,
            )
            if type(row) is not SurveyRoundView:
                raise SurveyRoundReadError("RESOURCE_NOT_FOUND")
            return row

        return self._run(query, "SURVEY_ROUND_GET", read)

    def _run(
        self, query: SurveyRoundReadQuery, operation: str,
        read: Callable[[object], object],
    ):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise SurveyRoundReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveyRoundReadError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                return read(tx)
        except SurveyRoundReadError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyRoundReadError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyRoundReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SurveyRoundReadError() from None

    @staticmethod
    def _validate_query(query: SurveyRoundReadQuery) -> None:
        if (type(query) is not SurveyRoundReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID
                or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID
                or query.project_id.int == 0):
            raise SurveyRoundReadError("VALIDATION_FAILED")
