"""Pure REVIEW_LIST query and projection contracts; no authorization by shape."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


REVIEW_LIST_VIEWS = frozenset({"all", "my_pending"})
_REVIEW_STATES = frozenset({"DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "WITHDRAWN"})
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_SUBJECT_CODE = re.compile(r"[A-Z][A-Z0-9_-]{0,63}\Z", re.ASCII)
_POLICY_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)


class ReviewListContractError(ValueError):
    def __init__(self) -> None:
        super().__init__("Review list contract unavailable")


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class ReviewListPosition:
    created_at: datetime
    review_id: UUID

    def __post_init__(self) -> None:
        if not _utc(self.created_at) or not _uuid(self.review_id):
            raise ReviewListContractError()


@dataclass(frozen=True, slots=True)
class ReviewListQuery:
    session_token: bytes = field(repr=False)
    trace_id: UUID
    project_id: UUID
    view: str = "all"
    before: ReviewListPosition | None = None
    page_size: int = 50

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not _uuid(self.trace_id) or not _uuid(self.project_id)
                or type(self.view) is not str or self.view not in REVIEW_LIST_VIEWS
                or self.before is not None and type(self.before) is not ReviewListPosition
                or type(self.page_size) is not int or not 1 <= self.page_size <= 200):
            raise ReviewListContractError()
        if self.before is not None:
            self.before.__post_init__()


@dataclass(frozen=True, slots=True)
class MyReviewAssignmentSummary:
    assignment_id: UUID
    state: str
    decision: str | None
    decided_at: datetime | None

    def __post_init__(self) -> None:
        pending = self.state == "PENDING"
        decided = self.state == "DECIDED"
        if (not _uuid(self.assignment_id) or not (pending or decided)
                or pending and (self.decision is not None or self.decided_at is not None)
                or decided and (self.decision not in ("APPROVE", "RETURN")
                                or not _utc(self.decided_at))):
            raise ReviewListContractError()


@dataclass(frozen=True, slots=True)
class ReviewListActiveRoundSummary:
    review_round_id: UUID
    round_no: int
    subject_version_id: UUID
    started_at: datetime
    my_assignment: MyReviewAssignmentSummary | None

    def __post_init__(self) -> None:
        if (not _uuid(self.review_round_id)
                or type(self.round_no) is not int or not 0 < self.round_no < 2**31
                or not _uuid(self.subject_version_id) or not _utc(self.started_at)
                or self.my_assignment is not None
                and type(self.my_assignment) is not MyReviewAssignmentSummary):
            raise ReviewListContractError()
        if self.my_assignment is not None:
            self.my_assignment.__post_init__()


@dataclass(frozen=True, slots=True)
class ReviewListItem:
    review_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    policy_code: str
    state: str
    created_by: UUID
    created_at: datetime
    etag: str
    active_round: ReviewListActiveRoundSummary | None

    @property
    def position(self) -> ReviewListPosition:
        return ReviewListPosition(self.created_at, self.review_id)

    def __post_init__(self) -> None:
        if (not all(_uuid(value) for value in (
                    self.review_id, self.project_id, self.subject_id, self.created_by))
                or type(self.subject_type) is not str
                or _SUBJECT_CODE.fullmatch(self.subject_type) is None
                or type(self.policy_code) is not str
                or _POLICY_CODE.fullmatch(self.policy_code) is None
                or type(self.state) is not str or self.state not in _REVIEW_STATES
                or not _utc(self.created_at)
                or type(self.etag) is not str or _ETAG.fullmatch(self.etag) is None
                or (self.state == "IN_REVIEW") != (self.active_round is not None)
                or self.active_round is not None
                and type(self.active_round) is not ReviewListActiveRoundSummary):
            raise ReviewListContractError()
        if self.active_round is not None:
            self.active_round.__post_init__()


@dataclass(frozen=True, slots=True)
class ReviewListPage:
    items: tuple[ReviewListItem, ...]
    next_position: ReviewListPosition | None
    has_more: bool

    def __post_init__(self) -> None:
        if (type(self.items) is not tuple
                or any(type(item) is not ReviewListItem for item in self.items)
                or type(self.has_more) is not bool
                or self.has_more != (self.next_position is not None)
                or self.next_position is not None
                and type(self.next_position) is not ReviewListPosition):
            raise ReviewListContractError()
        for item in self.items:
            item.__post_init__()
        if self.next_position is not None:
            self.next_position.__post_init__()
