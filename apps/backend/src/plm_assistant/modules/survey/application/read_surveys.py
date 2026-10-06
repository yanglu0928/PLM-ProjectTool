"""Authorized Survey identity and immutable definition read projections."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class SurveyReadError(RuntimeError):
    def __init__(self, code: str = "SURVEY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SurveyReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class SurveyView:
    survey_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    survey_state: str
    current_approved_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_by: uuid.UUID | None
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class SurveyOptionView:
    option_code: str
    label: str
    description: str | None
    ordinal: int


@dataclass(frozen=True, slots=True)
class SurveySourceView:
    source_kind: str
    handover_item_row_id: uuid.UUID | None
    handover_analysis_version_id: uuid.UUID | None
    handover_analysis_id: uuid.UUID | None
    capability_item_row_id: uuid.UUID | None
    capability_baseline_version_id: uuid.UUID | None
    capability_baseline_id: uuid.UUID | None
    template_document_version_id: uuid.UUID | None
    template_document_id: uuid.UUID | None
    manual_source_note: str | None
    ordinal: int


@dataclass(frozen=True, slots=True)
class SurveyQuestionView:
    question_id: uuid.UUID
    sequence_no: int
    topic: str
    question_text: str
    objective: str
    answer_type: str
    validation_rule: dict[str, object]
    required: bool
    condition_rule: dict[str, object] | None
    expected_output: str
    evidence_required: bool
    options: tuple[SurveyOptionView, ...] = ()
    sources: tuple[SurveySourceView, ...] = ()


@dataclass(frozen=True, slots=True)
class SurveyTargetDepartmentView:
    department_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class SurveyVersionView:
    survey_version_id: uuid.UUID
    survey_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    content_fingerprint: str
    declared_question_count: int
    declared_option_count: int
    declared_source_count: int
    declared_target_department_count: int
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    questions: tuple[SurveyQuestionView, ...] = ()
    target_departments: tuple[SurveyTargetDepartmentView, ...] = ()


@dataclass(frozen=True, slots=True)
class SurveyPage:
    items: tuple[SurveyView, ...]
    next_updated_at: datetime | None
    next_survey_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class SurveyVersionPage:
    items: tuple[SurveyVersionView, ...]
    next_version_no: int | None
    has_more: bool


class SurveyReadRepositoryPort(Protocol):
    def list_surveys(self, transaction: object, *, project_id: uuid.UUID,
                     after_updated_at: datetime | None,
                     after_survey_id: uuid.UUID | None,
                     limit: int) -> tuple[SurveyView, ...]: ...
    def get_survey(self, transaction: object, *, project_id: uuid.UUID,
                   survey_id: uuid.UUID) -> SurveyView | None: ...
    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      survey_id: uuid.UUID, after_version_no: int | None,
                      limit: int) -> tuple[SurveyVersionView, ...]: ...
    def get_version(self, transaction: object, *, project_id: uuid.UUID,
                    survey_id: uuid.UUID,
                    survey_version_id: uuid.UUID) -> SurveyVersionView | None: ...


class SurveyReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: SurveyReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Survey read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_surveys(
        self, query: SurveyReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_survey_id: uuid.UUID | None = None,
    ) -> SurveyPage:
        self._validate_query(query)
        self._validate_pair_position(page_size, after_updated_at, after_survey_id)
        return self._run(query, "SURVEY_LIST", lambda tx: self._survey_page(
            tx, query.project_id, page_size, after_updated_at, after_survey_id,
        ))

    def get_survey(self, query: SurveyReadQuery, survey_id: uuid.UUID) -> SurveyView:
        self._validate_query(query)
        self._identity(survey_id)

        def read(tx: object) -> SurveyView:
            row = self._repository.get_survey(
                tx, project_id=query.project_id, survey_id=survey_id,
            )
            if type(row) is not SurveyView:
                raise SurveyReadError("RESOURCE_NOT_FOUND")
            return row

        return self._run(query, "SURVEY_GET", read)

    def list_versions(
        self, query: SurveyReadQuery, *, survey_id: uuid.UUID,
        page_size: int, after_version_no: int | None = None,
    ) -> SurveyVersionPage:
        self._validate_query(query)
        self._identity(survey_id)
        self._validate_single_position(page_size, after_version_no)
        return self._run(query, "SURVEY_VERSION_LIST", lambda tx: self._version_page(
            tx, query.project_id, survey_id, page_size, after_version_no,
        ))

    def get_version(
        self, query: SurveyReadQuery, *, survey_id: uuid.UUID,
        survey_version_id: uuid.UUID,
    ) -> SurveyVersionView:
        self._validate_query(query)
        self._identity(survey_id)
        self._identity(survey_version_id)

        def read(tx: object) -> SurveyVersionView:
            row = self._repository.get_version(
                tx, project_id=query.project_id, survey_id=survey_id,
                survey_version_id=survey_version_id,
            )
            if type(row) is not SurveyVersionView:
                raise SurveyReadError("RESOURCE_NOT_FOUND")
            return row

        return self._run(query, "SURVEY_VERSION_GET", read)

    def _run(self, query: SurveyReadQuery, operation: str,
             read: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise SurveyReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise SurveyReadError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                return read(tx)
        except SurveyReadError:
            raise
        except ProjectAuthorizationError as error:
            raise SurveyReadError(error.code) from None
        except RuntimeLicenseError:
            raise SurveyReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise SurveyReadError() from None

    def _survey_page(self, tx: object, project_id: uuid.UUID, page_size: int,
                     after_updated_at: datetime | None,
                     after_survey_id: uuid.UUID | None) -> SurveyPage:
        rows = self._repository.list_surveys(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_survey_id=after_survey_id, limit=page_size + 1,
        )
        self._rows(rows, SurveyView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return SurveyPage(
            items, tail.updated_at if tail else None,
            tail.survey_id if tail else None, more,
        )

    def _version_page(self, tx: object, project_id: uuid.UUID,
                      survey_id: uuid.UUID, page_size: int,
                      after: int | None) -> SurveyVersionPage:
        rows = self._repository.list_versions(
            tx, project_id=project_id, survey_id=survey_id,
            after_version_no=after, limit=page_size + 1,
        )
        self._rows(rows, SurveyVersionView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return SurveyVersionPage(
            items, items[-1].version_no if more else None, more,
        )

    @staticmethod
    def _rows(rows: object, row_type: type, maximum: int) -> None:
        if (type(rows) is not tuple or len(rows) > maximum
                or any(type(row) is not row_type for row in rows)):
            raise SurveyReadError()

    @staticmethod
    def _validate_query(query: SurveyReadQuery) -> None:
        if (type(query) is not SurveyReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0):
            raise SurveyReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value: uuid.UUID) -> None:
        if type(value) is not uuid.UUID or value.int == 0:
            raise SurveyReadError("RESOURCE_NOT_FOUND")

    @staticmethod
    def _page_size(page_size: int) -> None:
        if type(page_size) is not int or not 1 <= page_size <= 200:
            raise SurveyReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_pair_position(cls, page_size: int,
                                updated_at: datetime | None,
                                survey_id: uuid.UUID | None) -> None:
        cls._page_size(page_size)
        if ((updated_at is None) != (survey_id is None)
                or updated_at is not None and (
                    type(updated_at) is not datetime
                    or updated_at.tzinfo is None
                    or updated_at.utcoffset() is None
                    or type(survey_id) is not uuid.UUID
                    or survey_id.int == 0)):
            raise SurveyReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_single_position(cls, page_size: int,
                                  position: int | None) -> None:
        cls._page_size(page_size)
        if (position is not None and (
                type(position) is not int or position <= 0)):
            raise SurveyReadError("VALIDATION_FAILED")
