"""Fail-closed dispatch for multiple PROJECT Review Subject Owners."""

from __future__ import annotations

from collections.abc import Iterable

from .create_review import _code
from .subject_start import ReviewSubjectAccessDenied


_METHODS = (
    "authorize_create",
    "authorize_replay",
    "prepare_start_in_transaction",
    "finalize_start_in_transaction",
    "assert_active_lock_in_transaction",
    "require_start_replay_access_in_transaction",
    "require_transition_access_in_transaction",
    "assert_transition_lock_in_transaction",
    "consume_terminal_in_transaction",
    "assert_terminal_consumed_in_transaction",
    "require_transition_replay_access_in_transaction",
)


class ProjectReviewSubjectRegistry:
    """Dispatch every Review callback to one registered Subject type."""

    def __init__(self, owners: Iterable[object]) -> None:
        if type(owners) not in (tuple, list):
            raise ValueError("Review Subject owners must be a bounded sequence")
        registered: dict[str, object] = {}
        for owner in owners:
            subject_type = getattr(owner, "SUBJECT_TYPE", None)
            if (not _code(subject_type, subject=True)
                    or subject_type in registered
                    or any(not callable(getattr(owner, method, None))
                           for method in _METHODS)):
                raise ValueError("Review Subject owner registration invalid")
            registered[subject_type] = owner
        if not registered:
            raise ValueError("At least one Review Subject owner is required")
        self._owners = registered

    def authorize_create(self, tx, *, user_id, project_id, subject_type,
                         subject_id, subject_version_id):
        owner = self._owners.get(subject_type)
        if owner is None:
            return None
        return owner.authorize_create(
            tx, user_id=user_id, project_id=project_id,
            subject_type=subject_type, subject_id=subject_id,
            subject_version_id=subject_version_id,
        )

    def authorize_replay(self, tx, *, user_id, review):
        owner = self._owners.get(getattr(review, "subject_type", None))
        return False if owner is None else owner.authorize_replay(
            tx, user_id=user_id, review=review,
        )

    def prepare_start_in_transaction(self, tx, request):
        return self._request_owner(request).prepare_start_in_transaction(tx, request)

    def finalize_start_in_transaction(self, tx, request):
        return self._request_owner(request).finalize_start_in_transaction(tx, request)

    def assert_active_lock_in_transaction(self, tx, request):
        return self._request_owner(request).assert_active_lock_in_transaction(tx, request)

    def require_start_replay_access_in_transaction(
        self, tx, *, actor_id, review, round_ref,
    ):
        return self._review_owner(review).require_start_replay_access_in_transaction(
            tx, actor_id=actor_id, review=review, round_ref=round_ref,
        )

    def require_transition_access_in_transaction(self, tx, transition):
        return self._transition_owner(transition).require_transition_access_in_transaction(
            tx, transition,
        )

    def assert_transition_lock_in_transaction(self, tx, transition):
        return self._transition_owner(transition).assert_transition_lock_in_transaction(
            tx, transition,
        )

    def consume_terminal_in_transaction(self, tx, transition):
        return self._transition_owner(transition).consume_terminal_in_transaction(
            tx, transition,
        )

    def assert_terminal_consumed_in_transaction(self, tx, transition):
        return self._transition_owner(transition).assert_terminal_consumed_in_transaction(
            tx, transition,
        )

    def require_transition_replay_access_in_transaction(
        self, tx, *, actor_id, review, result,
    ):
        return self._review_owner(
            review,
        ).require_transition_replay_access_in_transaction(
            tx, actor_id=actor_id, review=review, result=result,
        )

    def _request_owner(self, request):
        return self._review_owner(getattr(request, "review", None))

    def _transition_owner(self, transition):
        before = getattr(transition, "before", None)
        return self._review_owner(getattr(before, "review", None))

    def _review_owner(self, review):
        owner = self._owners.get(getattr(review, "subject_type", None))
        if owner is None:
            raise ReviewSubjectAccessDenied()
        return owner
