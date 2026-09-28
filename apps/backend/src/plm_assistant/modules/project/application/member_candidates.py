"""Exact, rate-limited candidate lookup for an authorized ProjectManager."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)


class ProjectMemberCandidateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class MemberCandidateQuery:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    username: str


@dataclass(frozen=True, slots=True)
class MemberCandidateView:
    user_id: uuid.UUID
    display_name: str


class MemberCandidateAccessPort(Protocol):
    def canonical_username(self, raw: str) -> str: ...
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...
    def enabled_user(self, transaction: object, *, normalized_username: str
                     ) -> tuple[uuid.UUID, str] | None: ...


class MemberCandidateMembershipPort(Protocol):
    def is_unassigned(self, transaction: object, *, user_id: uuid.UUID) -> bool: ...


class CandidateRatePort(Protocol):
    def reserve(self, transaction: object, *, bucket_key: bytes, limit: int,
                window: timedelta) -> bool: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectMemberCandidateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: MemberCandidateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 membership: MemberCandidateMembershipPort, rate: CandidateRatePort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, membership, rate)):
            raise ValueError("candidate lookup dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._membership, self._rate = authorization, membership, rate
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def exact(self, query: MemberCandidateQuery) -> MemberCandidateView | None:
        if (type(query) is not MemberCandidateQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.csrf_token) is not bytes or len(query.csrf_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(query.project_id) is not uuid.UUID or query.project_id.int == 0
                or type(query.username) is not str or len(query.username) > 255):
            raise ProjectMemberCandidateError("VALIDATION_FAILED")
        try:
            normalized = self._access.canonical_username(query.username)
        except ValueError:
            raise ProjectMemberCandidateError("VALIDATION_FAILED") from None
        if type(normalized) is not str or not 1 <= len(normalized) <= 128:
            raise ProjectMemberCandidateError("PROJECT_UNAVAILABLE")
        self._guard.require_valid(trace_id=query.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectMemberCandidateError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=query.session_token, csrf_token=query.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectMemberCandidateError("AUTH_ACCESS_DENIED")
            try:
                # The frozen create policy admits only a current manager of an ACTIVE project.
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="PROJECT_MEMBER_CREATE",
                )
            except ProjectAuthorizationError as exc:
                raise ProjectMemberCandidateError(exc.code) from None
            prefix = actor.bytes + query.project_id.bytes
            actor_key = hashlib.sha256(b"member-candidate-actor\x00" + prefix).digest()
            target_key = hashlib.sha256(
                b"member-candidate-target\x00" + prefix + normalized.encode("utf-8"),
            ).digest()
            actor_allowed = self._rate.reserve(
                tx, bucket_key=actor_key, limit=30, window=timedelta(minutes=5),
            )
            target_allowed = (self._rate.reserve(
                tx, bucket_key=target_key, limit=10, window=timedelta(minutes=5),
            ) if actor_allowed else False)
            if not actor_allowed or not target_allowed:
                tx.commit()  # Keep already consumed actor capacity on a target denial.
                raise ProjectMemberCandidateError("AUTH_RATE_LIMITED")
            candidate = self._access.enabled_user(tx, normalized_username=normalized)
            if candidate is not None and (type(candidate) is not tuple or len(candidate) != 2
                                          or type(candidate[0]) is not uuid.UUID
                                          or candidate[0].int == 0
                                          or type(candidate[1]) is not str
                                          or not candidate[1]):
                raise ProjectMemberCandidateError("PROJECT_UNAVAILABLE")
            if candidate is not None and not self._membership.is_unassigned(
                tx, user_id=candidate[0],
            ):
                candidate = None
            tx.commit()  # Count misses as well as hits across workers/processes.
            return MemberCandidateView(*candidate) if candidate is not None else None
