"""Per-request upload authorization; Session and project facts stay with their owners."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol


_UPLOAD_ROLES = frozenset({
    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER",
})


class DocumentUploadAccessError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SessionWriteAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class AdminWriteAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class ProjectFactsPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID, lock: bool = False) -> object | None: ...


class UploadOwnerPort(Protocol):
    def creator_id(self, transaction: object, *, upload_id: uuid.UUID,
                   scope: str, project_id: uuid.UUID | None) -> uuid.UUID | None: ...


class DocumentUploadAccess:
    """Recheck the live Session in each upload transaction, including after streaming."""

    def __init__(self, *, session_token: bytes, csrf_token: bytes,
                 session_access: SessionWriteAccessPort,
                 admin_access: AdminWriteAccessPort,
                 project_facts: ProjectFactsPort,
                 upload_owner: UploadOwnerPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32
                or any(item is None for item in (
                    session_access, admin_access, project_facts, upload_owner,
                ))):
            raise ValueError("valid request authorization dependencies are required")
        self._session_token, self._csrf_token = session_token, csrf_token
        self._session_access, self._admin_access = session_access, admin_access
        self._project_facts, self._upload_owner = project_facts, upload_owner
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               operation: str, target_document_id: uuid.UUID | None = None,
                               upload_id: uuid.UUID | None = None) -> None:
        if (type(actor_id) is not uuid.UUID or actor_id.int == 0
                or operation not in ("V1_DOCUMENT_UPLOAD_CREATE", "V1_DOCUMENT_UPLOAD_CONTENT",
                                     "V1_DOCUMENT_UPLOAD_COMMIT", "V1_DOCUMENT_UPLOAD_ABORT")
                or scope not in ("GLOBAL", "PROJECT")
                or (scope == "GLOBAL" and project_id is not None)
                or (scope == "PROJECT" and (type(project_id) is not uuid.UUID or project_id.int == 0))
                or (operation == "V1_DOCUMENT_UPLOAD_CREATE" and upload_id is not None)
                or (operation in ("V1_DOCUMENT_UPLOAD_CONTENT", "V1_DOCUMENT_UPLOAD_COMMIT",
                                  "V1_DOCUMENT_UPLOAD_ABORT") and (
                    type(upload_id) is not uuid.UUID or upload_id.int == 0
                    or target_document_id is not None))):
            raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise DocumentUploadAccessError("AUTH_ACCESS_DENIED")
        now = now.astimezone(timezone.utc)
        user_id = self._session_access.authenticated_user(
            transaction, session_token=self._session_token,
            csrf_token=self._csrf_token, now=now,
        )
        if user_id != actor_id:
            raise DocumentUploadAccessError("AUTH_ACCESS_DENIED")
        if scope == "GLOBAL":
            admin = self._admin_access.authorized_admin(
                transaction, session_token=self._session_token,
                csrf_token=self._csrf_token, now=now,
            )
            if admin != actor_id:
                raise DocumentUploadAccessError("AUTH_ACCESS_DENIED")
        else:
            facts = self._project_facts.actor_facts(
                transaction, user_id=actor_id, project_id=project_id, lock=True,
            )
            if facts is None or getattr(facts, "project_role", None) not in _UPLOAD_ROLES:
                raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
            if getattr(facts, "project_state", None) != "ACTIVE":
                raise DocumentUploadAccessError("PROJECT_ARCHIVED")
        if operation != "V1_DOCUMENT_UPLOAD_CREATE":
            creator = self._upload_owner.creator_id(
                transaction, upload_id=upload_id, scope=scope, project_id=project_id,
            )
            if creator != actor_id:
                raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
