"""Windows production composition for project AI Task metadata reads."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.ai.api.read_task import create_ai_task_read_router
from plm_assistant.modules.ai.application.task_read import AITaskReadService
from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class WindowsAITaskReadStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Task read unavailable")


def create_windows_ai_task_read_router(
    *, runtime: DatabaseRuntime, origins: LoginOriginPolicy, license_guard: object,
) -> APIRouter:
    try:
        if (not callable(getattr(runtime, "unit_of_work", None))
                or type(origins) is not LoginOriginPolicy or license_guard is None):
            raise WindowsAITaskReadStartupError()
        reads = AITaskReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            repository=SqlAlchemyAITaskReadRepository(),
        )
        return create_ai_task_read_router(reads=reads, origins=origins)
    except WindowsAITaskReadStartupError:
        raise
    except Exception:
        raise WindowsAITaskReadStartupError() from None
