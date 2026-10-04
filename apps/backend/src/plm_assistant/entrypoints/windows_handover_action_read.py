"""Fail-closed Windows composition for Handover Action LIST/GET."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.handover.api.action_list_cursor import (
    HandoverActionListCursorCodec,
)
from plm_assistant.modules.handover.api.read_actions import (
    create_handover_action_read_router,
)
from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionReadService,
)
from plm_assistant.modules.handover.infrastructure.action_read_repository import (
    SqlAlchemyHandoverActionReadRepository,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


HANDOVER_ACTION_CURSOR_KEY_REF = "handover-action-cursor-v1"


class HandoverActionKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionHandoverActionReadStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Handover Action read composition unavailable")


def create_windows_handover_action_read_router(
    runtime, *, sessions, origins, license_guard,
    resolver: HandoverActionKeyResolverPort | None = None,
) -> APIRouter:
    """Compose the read-only Handover Action boundary from explicit trust sources."""

    if any(value is None for value in (runtime, sessions, origins, license_guard)):
        raise ProductionHandoverActionReadStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        cursors = HandoverActionListCursorCodec(
            keys.resolve_key(HANDOVER_ACTION_CURSOR_KEY_REF),
        )
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        actions = HandoverActionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyHandoverActionReadRepository(),
        )
        return create_handover_action_read_router(
            sessions=sessions, actions=actions, origins=origins, cursors=cursors,
        )
    except Exception:
        raise ProductionHandoverActionReadStartupError() from None
