"""Explicit Windows write composition for OutputRequest creation."""
from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.entrypoints.output_requirement_source_adapter import (
    RequirementOutputSourceAdapter,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.jobs.application.output_enqueue import OutputJobQueue
from plm_assistant.modules.jobs.infrastructure.output_enqueue_repository import (
    SqlAlchemyOutputJobQueueRepository,
)
from plm_assistant.modules.output.api.create_request import (
    create_output_request_create_router,
)
from plm_assistant.modules.output.application.create_request import (
    OutputRequestService,
)
from plm_assistant.modules.output.application.resolve_context import (
    TrustedOutputContextResolver,
)
from plm_assistant.modules.output.infrastructure.builtin_policy_registry import (
    BuiltinOutputPolicyRegistry,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BuiltinOutputTemplateRegistry,
)
from plm_assistant.modules.output.infrastructure.create_request_repository import (
    SqlAlchemyOutputRequestRepository,
)
from plm_assistant.modules.output.infrastructure.plugin_operation_registry_adapter import (
    PluginOperationRegistryAdapter,
)
from plm_assistant.modules.output.infrastructure.create_access import (
    SqlAlchemyOutputRequestCreateAccess,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.plugin.application.operation_capability import (
    PluginOperationCapabilityReader,
)
from plm_assistant.modules.plugin.infrastructure.operation_capability_repository import (
    SqlAlchemyPluginOperationCapabilityRepository,
)
from plm_assistant.modules.plugin.infrastructure.packaged_signer_resolver import (
    PackagedPluginSignerResolver,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadService,
)
from plm_assistant.modules.requirement.infrastructure.version_read_repository import (
    SqlAlchemyRequirementVersionReadRepository,
)


class ProductionOutputCreateStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Output creation composition unavailable")


def create_windows_output_request_create_router(
    *, runtime, sessions, origins, license_guard, audit,
) -> APIRouter:
    if any(value is None for value in
           (runtime, sessions, origins, license_guard, audit)):
        raise ProductionOutputCreateStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        requirement_reads = RequirementVersionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyRequirementVersionReadRepository(),
        )
        operation_reader = PluginOperationCapabilityReader(
            SqlAlchemyPluginOperationCapabilityRepository(
                PackagedPluginSignerResolver(),
            ),
        )
        resolver = TrustedOutputContextResolver(
            sources=RequirementOutputSourceAdapter(requirement_reads),
            templates=BuiltinOutputTemplateRegistry(),
            policies=BuiltinOutputPolicyRegistry(),
            operations=PluginOperationRegistryAdapter(operation_reader),
        )
        service = OutputRequestService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyOutputRequestCreateAccess(
                authorization=authorization,
            ),
            license_guard=license_guard,
            resolver=resolver,
            repository=SqlAlchemyOutputRequestRepository(),
            jobs=OutputJobQueue(SqlAlchemyOutputJobQueueRepository()),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
        )
        return create_output_request_create_router(
            sessions=sessions, origins=origins, service=service,
        )
    except Exception:
        raise ProductionOutputCreateStartupError() from None
