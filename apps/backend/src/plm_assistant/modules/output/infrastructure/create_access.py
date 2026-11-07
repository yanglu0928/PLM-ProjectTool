"""Output-owned creator authorization adapter for Windows composition."""
from __future__ import annotations

import uuid
from datetime import datetime

from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.output.application.create_request import (
    OutputRequestAccessPort,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


class SqlAlchemyOutputRequestCreateAccess(OutputRequestAccessPort):
    """Authenticate Session/CSRF and authorize creation in the same UOW."""

    def __init__(self, *, authorization: ProjectAuthorizationService,
                 session_access: object | None = None) -> None:
        if authorization is None:
            raise ValueError("Output create authorization is required")
        self._authorization = authorization
        self._session_access = session_access or SqlAlchemyProjectWriteAccess()

    def authorized_creator(self, transaction: object, *, project_id: uuid.UUID,
                           session_token: bytes, csrf_token: bytes,
                           trace_id: uuid.UUID, now: datetime) -> uuid.UUID | None:
        del trace_id
        actor = self._session_access.authenticated_user(
            transaction, session_token=session_token,
            csrf_token=csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            return None
        try:
            facts = self._authorization.require_in_transaction(
                transaction, user_id=actor, project_id=project_id,
                operation="OUTPUT_REQUEST_CREATE",
            )
        except ProjectAuthorizationError:
            return None
        if (facts.user_id != actor or facts.project_id != project_id
                or facts.operation != "OUTPUT_REQUEST_CREATE"):
            return None
        return actor
