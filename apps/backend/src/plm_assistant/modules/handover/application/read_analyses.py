"""Authorized Handover Analysis, Version, and Item read projections."""

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


class HandoverAnalysisReadError(RuntimeError):
    def __init__(self, code: str = "HANDOVER_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HandoverAnalysisReadQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class HandoverAnalysisView:
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    analysis_purpose: str
    source_set_ref: str
    analysis_state: str
    current_approved_version_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class HandoverSourceDocumentView:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverAITaskView:
    ai_task_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverAnalysisVersionView:
    handover_analysis_version_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    version_state: str
    source_set_ref: str
    capability_baseline_id: uuid.UUID
    capability_baseline_version_ref: uuid.UUID
    content_fingerprint: str
    declared_source_count: int
    declared_item_count: int
    declared_evidence_count: int
    declared_capability_ref_count: int
    declared_ai_task_count: int
    supersedes_version_ref: uuid.UUID | None
    review_ref: uuid.UUID | None
    review_round_ref: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    source_documents: tuple[HandoverSourceDocumentView, ...] = ()
    ai_tasks: tuple[HandoverAITaskView, ...] = ()


@dataclass(frozen=True, slots=True)
class HandoverItemOptionView:
    option_code: str
    label: str
    description: str | None
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverItemCapabilityView:
    baseline_version_id: uuid.UUID
    capability_item_id: uuid.UUID
    ordinal: int


@dataclass(frozen=True, slots=True)
class HandoverAnalysisItemView:
    analysis_item_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    project_id: uuid.UUID
    ordinal: int
    item_type: str
    title: str
    statement: str
    impact: str
    severity: str
    priority: str
    recommendation: str | None
    confirmation_question: str | None
    required_input_spec: dict[str, object]
    source_missing: bool
    item_state: str
    evidence_refs: tuple[uuid.UUID, ...]
    capability_refs: tuple[HandoverItemCapabilityView, ...]
    options: tuple[HandoverItemOptionView, ...]


@dataclass(frozen=True, slots=True)
class HandoverAnalysisPage:
    items: tuple[HandoverAnalysisView, ...]
    next_updated_at: datetime | None
    next_handover_analysis_id: uuid.UUID | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class HandoverAnalysisVersionPage:
    items: tuple[HandoverAnalysisVersionView, ...]
    next_version_no: int | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class HandoverAnalysisItemPage:
    items: tuple[HandoverAnalysisItemView, ...]
    next_ordinal: int | None
    has_more: bool


class HandoverAnalysisReadRepositoryPort(Protocol):
    def list_analyses(self, transaction: object, *, project_id: uuid.UUID,
                      after_updated_at: datetime | None,
                      after_handover_analysis_id: uuid.UUID | None,
                      limit: int) -> tuple[HandoverAnalysisView, ...]: ...
    def get_analysis(self, transaction: object, *, project_id: uuid.UUID,
                     handover_analysis_id: uuid.UUID) -> HandoverAnalysisView | None: ...
    def list_versions(self, transaction: object, *, project_id: uuid.UUID,
                      handover_analysis_id: uuid.UUID,
                      after_version_no: int | None,
                      limit: int) -> tuple[HandoverAnalysisVersionView, ...]: ...
    def get_version(self, transaction: object, *, project_id: uuid.UUID,
                    handover_analysis_id: uuid.UUID,
                    handover_analysis_version_id: uuid.UUID,
                    ) -> HandoverAnalysisVersionView | None: ...
    def list_items(self, transaction: object, *, project_id: uuid.UUID,
                   handover_analysis_id: uuid.UUID,
                   handover_analysis_version_id: uuid.UUID,
                   after_ordinal: int | None,
                   limit: int) -> tuple[HandoverAnalysisItemView, ...]: ...


class HandoverAnalysisReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 license_guard: object, authorization: ProjectAuthorizationService,
                 repository: HandoverAnalysisReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, repository)):
            raise ValueError("Handover Analysis read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_analyses(
        self, query: HandoverAnalysisReadQuery, *, page_size: int,
        after_updated_at: datetime | None = None,
        after_handover_analysis_id: uuid.UUID | None = None,
    ) -> HandoverAnalysisPage:
        self._validate_query(query)
        self._validate_pair_position(
            page_size, after_updated_at, after_handover_analysis_id,
        )
        return self._run(query, "HND_ANALYSIS_LIST", lambda tx: self._analysis_page(
            tx, query.project_id, page_size, after_updated_at,
            after_handover_analysis_id,
        ))

    def get_analysis(self, query: HandoverAnalysisReadQuery,
                     handover_analysis_id: uuid.UUID) -> HandoverAnalysisView:
        self._validate_query(query)
        self._identity(handover_analysis_id)
        def read(tx: object) -> HandoverAnalysisView:
            row = self._repository.get_analysis(
                tx, project_id=query.project_id,
                handover_analysis_id=handover_analysis_id,
            )
            if type(row) is not HandoverAnalysisView:
                raise HandoverAnalysisReadError("RESOURCE_NOT_FOUND")
            return row
        return self._run(query, "HND_ANALYSIS_GET", read)

    def list_versions(
        self, query: HandoverAnalysisReadQuery, *, handover_analysis_id: uuid.UUID,
        page_size: int, after_version_no: int | None = None,
    ) -> HandoverAnalysisVersionPage:
        self._validate_query(query)
        self._identity(handover_analysis_id)
        self._validate_single_position(page_size, after_version_no, allow_zero=False)
        return self._run(query, "HND_VERSION_LIST", lambda tx: self._version_page(
            tx, query.project_id, handover_analysis_id, page_size, after_version_no,
        ))

    def get_version(
        self, query: HandoverAnalysisReadQuery, *, handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID,
    ) -> HandoverAnalysisVersionView:
        self._validate_query(query)
        self._identity(handover_analysis_id)
        self._identity(handover_analysis_version_id)
        def read(tx: object) -> HandoverAnalysisVersionView:
            row = self._repository.get_version(
                tx, project_id=query.project_id,
                handover_analysis_id=handover_analysis_id,
                handover_analysis_version_id=handover_analysis_version_id,
            )
            if type(row) is not HandoverAnalysisVersionView:
                raise HandoverAnalysisReadError("RESOURCE_NOT_FOUND")
            return row
        return self._run(query, "HND_VERSION_GET", read)

    def list_items(
        self, query: HandoverAnalysisReadQuery, *, handover_analysis_id: uuid.UUID,
        handover_analysis_version_id: uuid.UUID, page_size: int,
        after_ordinal: int | None = None,
    ) -> HandoverAnalysisItemPage:
        self._validate_query(query)
        self._identity(handover_analysis_id)
        self._identity(handover_analysis_version_id)
        self._validate_single_position(page_size, after_ordinal, allow_zero=True)
        return self._run(query, "HND_VERSION_ITEM_LIST", lambda tx: self._item_page(
            tx, query.project_id, handover_analysis_id,
            handover_analysis_version_id, page_size, after_ordinal,
        ))

    def _run(self, query: HandoverAnalysisReadQuery, operation: str,
             read: Callable[[object], object]):
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise HandoverAnalysisReadError()
                actor = self._access.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise HandoverAnalysisReadError("AUTH_ACCESS_DENIED")
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                return read(tx)
        except HandoverAnalysisReadError:
            raise
        except ProjectAuthorizationError as error:
            raise HandoverAnalysisReadError(error.code) from None
        except RuntimeLicenseError:
            raise HandoverAnalysisReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise HandoverAnalysisReadError() from None

    def _analysis_page(self, tx: object, project_id: uuid.UUID, page_size: int,
                       after_updated_at: datetime | None,
                       after_id: uuid.UUID | None) -> HandoverAnalysisPage:
        rows = self._repository.list_analyses(
            tx, project_id=project_id, after_updated_at=after_updated_at,
            after_handover_analysis_id=after_id, limit=page_size + 1,
        )
        self._rows(rows, HandoverAnalysisView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        tail = items[-1] if more else None
        return HandoverAnalysisPage(
            items, tail.updated_at if tail else None,
            tail.handover_analysis_id if tail else None, more,
        )

    def _version_page(self, tx: object, project_id: uuid.UUID,
                      analysis_id: uuid.UUID, page_size: int,
                      after: int | None) -> HandoverAnalysisVersionPage:
        rows = self._repository.list_versions(
            tx, project_id=project_id, handover_analysis_id=analysis_id,
            after_version_no=after, limit=page_size + 1,
        )
        self._rows(rows, HandoverAnalysisVersionView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return HandoverAnalysisVersionPage(
            items, items[-1].version_no if more else None, more,
        )

    def _item_page(self, tx: object, project_id: uuid.UUID,
                   analysis_id: uuid.UUID, version_id: uuid.UUID,
                   page_size: int, after: int | None) -> HandoverAnalysisItemPage:
        rows = self._repository.list_items(
            tx, project_id=project_id, handover_analysis_id=analysis_id,
            handover_analysis_version_id=version_id,
            after_ordinal=after, limit=page_size + 1,
        )
        self._rows(rows, HandoverAnalysisItemView, page_size + 1)
        items, more = rows[:page_size], len(rows) > page_size
        return HandoverAnalysisItemPage(
            items, items[-1].ordinal if more else None, more,
        )

    @staticmethod
    def _rows(rows: object, row_type: type, maximum: int) -> None:
        if (type(rows) is not tuple or len(rows) > maximum
                or any(type(row) is not row_type for row in rows)):
            raise HandoverAnalysisReadError()

    @staticmethod
    def _validate_query(query: HandoverAnalysisReadQuery) -> None:
        if (type(query) is not HandoverAnalysisReadQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0):
            raise HandoverAnalysisReadError("VALIDATION_FAILED")

    @staticmethod
    def _identity(value: uuid.UUID) -> None:
        if type(value) is not uuid.UUID or value.int == 0:
            raise HandoverAnalysisReadError("RESOURCE_NOT_FOUND")

    @staticmethod
    def _page_size(page_size: int) -> None:
        if type(page_size) is not int or not 1 <= page_size <= 200:
            raise HandoverAnalysisReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_pair_position(cls, page_size: int,
                                updated_at: datetime | None,
                                analysis_id: uuid.UUID | None) -> None:
        cls._page_size(page_size)
        if ((updated_at is None) != (analysis_id is None)
                or updated_at is not None and (
                    type(updated_at) is not datetime
                    or updated_at.tzinfo is None
                    or updated_at.utcoffset() is None
                    or type(analysis_id) is not uuid.UUID
                    or analysis_id.int == 0)):
            raise HandoverAnalysisReadError("VALIDATION_FAILED")

    @classmethod
    def _validate_single_position(cls, page_size: int, position: int | None,
                                  *, allow_zero: bool) -> None:
        cls._page_size(page_size)
        if (position is not None and (
                type(position) is not int or position < 0
                or position == 0 and not allow_zero)):
            raise HandoverAnalysisReadError("VALIDATION_FAILED")
