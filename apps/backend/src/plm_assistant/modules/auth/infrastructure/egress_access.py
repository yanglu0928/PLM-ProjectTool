"""Auth-owned Session adapter for Egress read and write application ports."""

from __future__ import annotations

import uuid
from datetime import datetime

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)


class SqlAlchemyEgressAccess:
    """Dispatch GET proof to read access and mutations to CSRF-bound write access."""

    def __init__(self) -> None:
        self._reads = SqlAlchemyProjectReadAccess()
        self._writes = SqlAlchemyProjectWriteAccess()

    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes | None, now: datetime) -> uuid.UUID | None:
        if csrf_token is None:
            return self._reads.authenticated_user(
                transaction, session_token=session_token, now=now,
            )
        return self._writes.authenticated_user(
            transaction, session_token=session_token, csrf_token=csrf_token, now=now,
        )
