"""Single owned transition intent, never an authorization or Owner lock proof."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .read_snapshot import FixedReviewRoundSnapshot
from ..domain.round_progress import ReviewRoundProgress, ReviewRoundState, _utc, _uuid


class ReviewSubjectTransitionError(ValueError):
    def __init__(self):
        super().__init__("Review Subject transition unavailable")


@dataclass(frozen=True, slots=True)
class ReviewSubjectTransition:
    actor_id: UUID
    trace_id: UUID
    before: FixedReviewRoundSnapshot
    after_progress: ReviewRoundProgress
    occurred_at: datetime

    def __post_init__(self):
        if (not _uuid(self.actor_id) or not _uuid(self.trace_id) or not _utc(self.occurred_at)
                or type(self.before) is not FixedReviewRoundSnapshot
                or type(self.after_progress) is not ReviewRoundProgress):
            raise ReviewSubjectTransitionError()
        try:
            self.before.__post_init__()
            self.after_progress.__post_init__()
            old = self.before.progress
            new = self.after_progress
            if (self.before.review.scope != "PROJECT"
                    or old.state is not ReviewRoundState.IN_REVIEW
                    or self.before.round_lock_version >= 2**63 - 1
                    or self.before.review.lock_version >= 2**63 - 1):
                raise ReviewSubjectTransitionError()
            if new.withdrawal is not None:
                withdrawal = new.withdrawal
                if (withdrawal.actor_id != self.actor_id or withdrawal.occurred_at != self.occurred_at
                        or new != old.withdraw(withdrawal)):
                    raise ReviewSubjectTransitionError()
            else:
                if len(new.decisions) != len(old.decisions) + 1:
                    raise ReviewSubjectTransitionError()
                decision = new.decisions[-1]
                if (decision.reviewer_id != self.actor_id or decision.decided_at != self.occurred_at
                        or new != old.record_decision(decision)):
                    raise ReviewSubjectTransitionError()
        except ValueError:
            raise ReviewSubjectTransitionError() from None

    @property
    def terminal(self) -> bool:
        self.__post_init__()
        return self.after_progress.state is not ReviewRoundState.IN_REVIEW

    def require_binding(self, expected: "ReviewSubjectTransition") -> None:
        self.__post_init__()
        if type(expected) is not ReviewSubjectTransition:
            raise ReviewSubjectTransitionError()
        expected.__post_init__()
        if self != expected:
            raise ReviewSubjectTransitionError()


class ReviewSubjectTransitionPort(Protocol):
    """Registered actual Owner only; all calls use the caller's SAME transaction.

    Require current Actor/version/policy-specific permissions and REAL identity
    lock binding, including protection against edits and replacement drafts.
    Never authorize by DTO construction, historical qualification or True.

    Consume only a terminal transition. APPROVED rechecks current immutable
    content and necessary Sources/qualifications before Owner formalization;
    RETURNED/WITHDRAWN do not approve a version. Consume the bound result and
    release the actual Owner lock atomically with Review rows, Audit and receipt.
    On any failure raise and roll back everything, including the final decision.
    No commit, foreign SQL, background best-effort notification or default Owner.
    Replays require separate CURRENT historical-version access, not consumption.
    """
    def require_transition_access_in_transaction(self, tx: object, transition: ReviewSubjectTransition) -> None: ...
    def assert_transition_lock_in_transaction(self, tx: object, transition: ReviewSubjectTransition) -> None: ...
    def consume_terminal_in_transaction(self, tx: object, transition: ReviewSubjectTransition) -> None: ...
