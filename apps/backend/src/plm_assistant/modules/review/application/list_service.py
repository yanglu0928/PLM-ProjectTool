"""Authorized PROJECT Review pages; candidate Assignment is never authority."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS,
    AuthorizedProjectAction,
    ProjectAuthorizationError,
)

from .list_contract import (
    ReviewListContractError,
    ReviewListItem,
    ReviewListPage,
    ReviewListPosition,
    ReviewListQuery,
)
from .read_service import AuthorizedReviewSubjectRead, ReviewSubjectReadPort


class ReviewListError(RuntimeError):
    def __init__(self, code: str = "REVIEW_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class ReviewListRepositoryPort(Protocol):
    def list_candidates(
        self,
        transaction: object,
        *,
        project_id: UUID,
        actor_id: UUID,
        view: str,
        before: ReviewListPosition | None,
        limit: int,
    ) -> tuple[ReviewListItem, ...]: ...


def _key(position: ReviewListPosition) -> tuple[datetime, int]:
    return position.created_at.astimezone(timezone.utc), position.review_id.int


class ReviewListService:
    def __init__(
        self,
        *,
        unit_of_work: Callable[[], object],
        sessions: object,
        projects: object,
        license_guard: object,
        repository: ReviewListRepositoryPort,
        subjects: ReviewSubjectReadPort,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, sessions, projects, license_guard, repository, subjects,
        )):
            raise ValueError("Review list dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._repository, self._subjects = (
            license_guard, repository, subjects,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _proof_matches(
        proof: object,
        *,
        actor_id: UUID,
        item: ReviewListItem,
        subject_version_id: UUID | None,
    ) -> bool:
        return (
            type(proof) is AuthorizedReviewSubjectRead
            and proof.user_id == actor_id
            and proof.project_id == item.project_id
            and proof.subject_type == item.subject_type
            and proof.subject_id == item.subject_id
            and proof.subject_version_id == subject_version_id
        )

    def _subject_visible(
        self, transaction: object, actor_id: UUID, item: ReviewListItem,
    ) -> bool:
        identity = self._subjects.authorize_read(
            transaction,
            user_id=actor_id,
            project_id=item.project_id,
            subject_type=item.subject_type,
            subject_id=item.subject_id,
            subject_version_id=None,
        )
        if not self._proof_matches(
            identity, actor_id=actor_id, item=item, subject_version_id=None,
        ):
            return False
        if item.active_round is None:
            return True
        version = item.active_round.subject_version_id
        fixed = self._subjects.authorize_read(
            transaction,
            user_id=actor_id,
            project_id=item.project_id,
            subject_type=item.subject_type,
            subject_id=item.subject_id,
            subject_version_id=version,
        )
        return self._proof_matches(
            fixed, actor_id=actor_id, item=item, subject_version_id=version,
        )

    @staticmethod
    def _validate_candidates(
        query: ReviewListQuery,
        candidates: object,
    ) -> tuple[ReviewListItem, ...]:
        if type(candidates) is not tuple or len(candidates) > query.page_size + 1:
            raise ReviewListContractError()
        positions: list[tuple[datetime, int]] = []
        identities: set[UUID] = set()
        for item in candidates:
            if type(item) is not ReviewListItem:
                raise ReviewListContractError()
            item.__post_init__()
            if item.project_id != query.project_id or item.review_id in identities:
                raise ReviewListContractError()
            if query.view == "my_pending" and (
                item.active_round is None
                or item.active_round.my_assignment is None
                or item.active_round.my_assignment.state != "PENDING"
            ):
                raise ReviewListContractError()
            identities.add(item.review_id)
            positions.append(_key(item.position))
        if any(left <= right for left, right in zip(
            positions, positions[1:], strict=False,
        )):
            raise ReviewListContractError()
        if query.before is not None and positions and positions[0] >= _key(query.before):
            raise ReviewListContractError()
        return candidates

    def list(self, query: ReviewListQuery) -> ReviewListPage:
        if type(query) is not ReviewListQuery:
            raise ReviewListError("VALIDATION_FAILED")
        try:
            query.__post_init__()
        except ReviewListContractError:
            raise ReviewListError("VALIDATION_FAILED") from None
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if (type(now) is not datetime or now.tzinfo is None
                        or now.utcoffset() is None):
                    raise ReviewListError()
                actor = self._sessions.authenticated_user(
                    transaction,
                    session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not UUID or actor.int == 0:
                    raise ReviewListError("AUTH_ACCESS_DENIED")
                project = self._projects.require_in_transaction(
                    transaction,
                    user_id=actor,
                    project_id=query.project_id,
                    operation="REVIEW_LIST",
                )
                if (
                    type(project) is not AuthorizedProjectAction
                    or project.user_id != actor
                    or project.project_id != query.project_id
                    or project.operation != "REVIEW_LIST"
                    or project.project_role not in ALL_MEMBERS
                ):
                    raise ReviewListError("RESOURCE_NOT_FOUND")
                candidates = self._validate_candidates(
                    query,
                    self._repository.list_candidates(
                        transaction,
                        project_id=query.project_id,
                        actor_id=actor,
                        view=query.view,
                        before=query.before,
                        limit=query.page_size + 1,
                    ),
                )
                has_more = len(candidates) > query.page_size
                consumed = candidates[:query.page_size]
                visible = tuple(
                    item for item in consumed
                    if self._subject_visible(transaction, actor, item)
                )
                self._guard.require_valid(trace_id=query.trace_id)
                return ReviewListPage(
                    visible,
                    consumed[-1].position if has_more else None,
                    has_more,
                )
        except ReviewListError:
            raise
        except ProjectAuthorizationError:
            raise ReviewListError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise ReviewListError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReviewListError() from None
