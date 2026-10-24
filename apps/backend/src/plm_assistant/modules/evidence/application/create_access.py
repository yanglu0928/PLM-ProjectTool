"""Current request identity and role boundary for Evidence candidates.

This does not prove a DocumentVersion or Locator and is not a creation route.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.project.application.authorization import ProjectActorFacts


_PROJECT_CREATORS = frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"})
_OPERATION = "V1_EVIDENCE_CREATE"


class EvidenceCreateAccessError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvidenceSessionWritePort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class EvidenceAdminWritePort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class EvidenceProjectFactsPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...


class EvidenceCreateAccess:
    """Recheck live Session, CSRF and role within each candidate transaction."""

    def __init__(self, *, session_token: bytes, csrf_token: bytes,
                 session_access: EvidenceSessionWritePort,
                 admin_access: EvidenceAdminWritePort,
                 project_facts: EvidenceProjectFactsPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32
                or any(item is None for item in (session_access, admin_access,
                                                 project_facts))):
            raise ValueError("valid Evidence access dependencies are required")
        self._session_token, self._csrf_token = session_token, csrf_token
        self._session_access, self._admin_access = session_access, admin_access
        self._project_facts = project_facts
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               document_id: uuid.UUID, operation: str) -> None:
        if (transaction is None
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(document_id) is not uuid.UUID or document_id.int == 0
                or operation != _OPERATION
                or scope not in ("GLOBAL", "PROJECT")
                or scope == "GLOBAL" and project_id is not None
                or scope == "PROJECT" and (
                    type(project_id) is not uuid.UUID or project_id.int == 0)):
            raise EvidenceCreateAccessError("RESOURCE_NOT_FOUND")
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise EvidenceCreateAccessError("AUTH_ACCESS_DENIED")
        now = now.astimezone(timezone.utc)
        user_id = self._session_access.authenticated_user(
            transaction, session_token=self._session_token,
            csrf_token=self._csrf_token, now=now,
        )
        if user_id != actor_id:
            raise EvidenceCreateAccessError("AUTH_ACCESS_DENIED")
        if scope == "GLOBAL":
            if self._admin_access.authorized_admin(
                    transaction, session_token=self._session_token,
                    csrf_token=self._csrf_token, now=now) != actor_id:
                raise EvidenceCreateAccessError("AUTH_ACCESS_DENIED")
        else:
            facts = self._project_facts.actor_facts(
                transaction, user_id=actor_id, project_id=project_id, lock=True,
            )
            if type(facts) is not ProjectActorFacts or facts.project_role not in _PROJECT_CREATORS:
                raise EvidenceCreateAccessError("RESOURCE_NOT_FOUND")
            if facts.project_state != "ACTIVE":
                raise EvidenceCreateAccessError("PROJECT_ARCHIVED")
