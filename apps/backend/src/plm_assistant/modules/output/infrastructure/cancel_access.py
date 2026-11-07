"""Output-owned cancellation authorization adapter for the Windows composition."""
from __future__ import annotations

import uuid
from datetime import datetime

from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.output.application.cancel_request import (
    OutputRequestCancelAccessPort,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


class SqlAlchemyOutputRequestCancelAccess(OutputRequestCancelAccessPort):
    """Authenticate in the caller UOW; allow the creator or a Project Manager."""

    def __init__(self, *, authorization: ProjectAuthorizationService,
                 session_access: object | None = None) -> None:
        if authorization is None:
            raise ValueError("Output cancel authorization is required")
        self._authorization = authorization
        self._session_access = session_access or SqlAlchemyProjectWriteAccess()

    def authenticated_user(self, transaction: object, *, session_token: bytes,
                          csrf_token: bytes, now: datetime) -> uuid.UUID | None:
        return self._session_access.authenticated_user(
            transaction, session_token=session_token, csrf_token=csrf_token, now=now,
        )

    def require_canceller(self, transaction: object, *, user_id: uuid.UUID,
                          project_id: uuid.UUID, requester_id: uuid.UUID) -> bool:
        if user_id == requester_id:
            return True
        try:
            self._authorization.require_in_transaction(
                transaction, user_id=user_id, project_id=project_id,
                operation="OUTPUT_REQUEST_CANCEL",
            )
        except ProjectAuthorizationError:
            return False
        return True
