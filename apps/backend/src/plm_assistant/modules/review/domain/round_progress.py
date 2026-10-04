"""DM-02 complete-set aggregation; not identity/Subject/approval proof.

This owned progress value is not the full ReviewRound Aggregate. Applications
must authenticate, check License/scope/assignments and lock the actual Subject.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class ReviewProgressError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid Review round progress")


class ReviewDecisionKind(StrEnum):
    APPROVE = "APPROVE"
    RETURN = "RETURN"


class ReviewRoundState(StrEnum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    RETURNED = "RETURNED"
    WITHDRAWN = "WITHDRAWN"


def _uuid(value: object) -> bool:
    return type(value) is UUID and value.int != 0


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _comment(value: object) -> bool:
    # No new public length limit: SC-02 LONG_TEXT has an application quota.
    return value is None or type(value) is str and "\x00" not in value


@dataclass(frozen=True, slots=True)
class ReviewDecisionSnapshot:
    decision_id: UUID
    round_id: UUID
    reviewer_id: UUID
    kind: ReviewDecisionKind
    decided_at: datetime
    comment: str | None = None

    def __post_init__(self) -> None:
        if (not all(_uuid(v) for v in (self.decision_id, self.round_id, self.reviewer_id))
                or type(self.kind) is not ReviewDecisionKind or not _utc(self.decided_at)
                or not _comment(self.comment)
                or self.kind is ReviewDecisionKind.RETURN
                and (self.comment is None or not self.comment.strip())):
            raise ReviewProgressError()


@dataclass(frozen=True, slots=True)
class ReviewWithdrawalSnapshot:
    actor_id: UUID
    occurred_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        if (not _uuid(self.actor_id) or not _utc(self.occurred_at)
                or not _comment(self.reason)
                or self.reason is not None and not self.reason.strip()):
            raise ReviewProgressError()


@dataclass(frozen=True, slots=True)
class ReviewRoundProgress:
    round_id: UUID
    started_at: datetime
    reviewer_ids: tuple[UUID, ...]
    decisions: tuple[ReviewDecisionSnapshot, ...] = ()
    withdrawal: ReviewWithdrawalSnapshot | None = None

    def __post_init__(self) -> None:
        if (not _uuid(self.round_id) or not _utc(self.started_at)
                or type(self.reviewer_ids) is not tuple or not self.reviewer_ids
                or not all(_uuid(v) for v in self.reviewer_ids)
                or len(set(self.reviewer_ids)) != len(self.reviewer_ids)
                or type(self.decisions) is not tuple
                or any(type(d) is not ReviewDecisionSnapshot for d in self.decisions)):
            raise ReviewProgressError()
        reviewer_set, decision_set = set(), set()
        for decision in self.decisions:
            decision.__post_init__()
            if (decision.round_id != self.round_id or decision.reviewer_id not in self.reviewer_ids
                    or decision.reviewer_id in reviewer_set or decision.decision_id in decision_set
                    or decision.decided_at < self.started_at):
                raise ReviewProgressError()
            reviewer_set.add(decision.reviewer_id)
            decision_set.add(decision.decision_id)
        if self.withdrawal is not None:
            if type(self.withdrawal) is not ReviewWithdrawalSnapshot:
                raise ReviewProgressError()
            self.withdrawal.__post_init__()
            if (len(self.decisions) == len(self.reviewer_ids)
                    or self.withdrawal.occurred_at < self.started_at
                    or any(d.decided_at > self.withdrawal.occurred_at for d in self.decisions)):
                raise ReviewProgressError()

    @property
    def state(self) -> ReviewRoundState:
        self.__post_init__()
        if self.withdrawal is not None:
            return ReviewRoundState.WITHDRAWN
        if len(self.decisions) < len(self.reviewer_ids):
            return ReviewRoundState.IN_REVIEW
        return (ReviewRoundState.RETURNED if any(d.kind is ReviewDecisionKind.RETURN for d in self.decisions)
                else ReviewRoundState.APPROVED)

    @property
    def pending_reviewer_ids(self) -> tuple[UUID, ...]:
        self.__post_init__()
        decided = {d.reviewer_id for d in self.decisions}
        return tuple(v for v in self.reviewer_ids if v not in decided)

    def record_decision(self, decision: ReviewDecisionSnapshot) -> "ReviewRoundProgress":
        if self.state is not ReviewRoundState.IN_REVIEW:
            raise ReviewProgressError()
        return replace(self, decisions=self.decisions + (decision,))

    def withdraw(self, withdrawal: ReviewWithdrawalSnapshot) -> "ReviewRoundProgress":
        if self.state is not ReviewRoundState.IN_REVIEW or type(withdrawal) is not ReviewWithdrawalSnapshot:
            raise ReviewProgressError()
        return replace(self, withdrawal=withdrawal)
