"""Windows production composition for frozen AI Task read surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.ai.api.list_invocations import create_ai_invocation_list_router
from plm_assistant.modules.ai.api.list_tasks import create_ai_task_list_router
from plm_assistant.modules.ai.api.read_suggestion import create_ai_suggestion_read_router
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.invocation_read import AIInvocationListService
from plm_assistant.modules.ai.application.output_schema import (
    default_ai_output_schema_registry,
)
from plm_assistant.modules.ai.application.suggestion_read import AISuggestionReadService
from plm_assistant.modules.ai.application.task_read import AITaskListService
from plm_assistant.modules.ai.infrastructure.invocation_read_repository import (
    SqlAlchemyAIInvocationReadRepository,
)
from plm_assistant.modules.ai.infrastructure.suggestion_read_repository import (
    SqlAlchemyAISuggestionReadRepository,
)
from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocationService,
    DocumentVersionLocationService,
)
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class WindowsAIReadStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI read surfaces unavailable")


@dataclass(frozen=True, slots=True)
class WindowsAIReadRouters:
    tasks: APIRouter
    invocations: APIRouter
    suggestion: APIRouter


def create_windows_ai_read_routers(
    *, runtime: DatabaseRuntime, origins: LoginOriginPolicy,
    license_guard: object, task_cursors: AITaskListCursorCodec,
    invocation_cursors: AIInvocationListCursorCodec,
    documents: object, parse_results: object,
) -> WindowsAIReadRouters:
    try:
        if (not callable(getattr(runtime, "unit_of_work", None))
                or type(origins) is not LoginOriginPolicy
                or license_guard is None
                or type(task_cursors) is not AITaskListCursorCodec
                or type(invocation_cursors) is not AIInvocationListCursorCodec
                or not callable(getattr(documents, "get_version", None))
                or not callable(getattr(parse_results, "read", None))):
            raise WindowsAIReadStartupError()
        authorization = lambda: ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        access = SqlAlchemyProjectReadAccess()
        tasks = SqlAlchemyAITaskReadRepository()
        task_reads = AITaskListService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization(),
            repository=tasks,
        )
        invocation_reads = AIInvocationListService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization(),
            tasks=tasks, invocations=SqlAlchemyAIInvocationReadRepository(),
        )
        suggestion_reads = AISuggestionReadService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization(),
            repository=SqlAlchemyAISuggestionReadRepository(),
            schemas=default_ai_output_schema_registry(),
            document_nodes=DocumentNodeLocationService(results=parse_results),
            document_versions=DocumentVersionLocationService(versions=documents),
        )
        return WindowsAIReadRouters(
            create_ai_task_list_router(
                reads=task_reads, origins=origins, cursors=task_cursors,
            ),
            create_ai_invocation_list_router(
                reads=invocation_reads, origins=origins,
                cursors=invocation_cursors,
            ),
            create_ai_suggestion_read_router(
                reads=suggestion_reads, origins=origins,
            ),
        )
    except WindowsAIReadStartupError:
        raise
    except Exception:
        raise WindowsAIReadStartupError() from None
