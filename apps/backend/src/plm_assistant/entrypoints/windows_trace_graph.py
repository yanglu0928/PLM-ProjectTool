"""Explicit Windows read composition for the frozen Trace graph endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from plm_assistant.entrypoints.trace_document_owner import DocumentVersionTraceOwner
from plm_assistant.entrypoints.trace_plan_wbs_owner import PlanWbsTraceOwner
from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.entrypoints.trace_structured_spec_owner import StructuredSpecTraceOwner
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.plan.application.read_wbs_for_trace import PlanWbsTraceReadService
from plm_assistant.modules.plan.infrastructure.wbs_trace_read_repository import SqlAlchemyPlanWbsTraceReadRepository
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadService
from plm_assistant.modules.solution.application.read_structured_spec import StructuredSpecReadService
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.solution.infrastructure.structured_spec_read_repository import SqlAlchemyStructuredSpecReadRepository
from plm_assistant.modules.trace.api.graph import create_trace_graph_router
from plm_assistant.modules.trace.application.page_graph import TraceGraphCursorCodec, TraceGraphPageService
from plm_assistant.modules.trace.application.query_bounded_graph import TraceBoundedGraphService
from plm_assistant.modules.trace.application.read_public_graph import TracePublicGraphReadService
from plm_assistant.modules.trace.application.target_proof import TracePublicEdgeResolver, TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.query_repository import SqlAlchemyTraceAdjacencyRepository


class ProductionTraceGraphStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Trace graph production composition unavailable")


def create_windows_trace_graph_router(
    *, runtime, sessions, origins, license_guard,
    cursors: TraceGraphCursorCodec,
) -> APIRouter:
    """Build an opt-in graph route without generating or reading its cursor key."""
    if (any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors))
            or type(cursors) is not TraceGraphCursorCodec):
        raise ProductionTraceGraphStartupError()
    try:
        read_access = SqlAlchemyProjectReadAccess()
        project_facts = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_facts)
        owners = {
            ("document", "DOC-02"): DocumentVersionTraceOwner(DocumentReadService(
                unit_of_work=runtime.unit_of_work,
                session_access=read_access,
                admin_access=SqlAlchemyDeploymentReadAccess(),
                project_facts=project_facts, license_guard=license_guard,
                repository=SqlAlchemyDocumentReadRepository())),
            ("requirement", "REQ-03"): RequirementVersionTraceOwner(
                RequirementVersionReadService(
                    unit_of_work=runtime.unit_of_work, access=read_access,
                    license_guard=license_guard, authorization=authorization,
                    repository=SqlAlchemyRequirementVersionReadRepository())),
            ("solution", "SOL-05"): SectionVersionTraceOwner(
                SectionVersionReadService(
                    unit_of_work=runtime.unit_of_work, access=read_access,
                    license_guard=license_guard, authorization=authorization,
                    sections=SqlAlchemySectionReadRepository(),
                    versions=SqlAlchemySectionVersionReadRepository())),
            ("solution", "SOL-06"): StructuredSpecTraceOwner(
                StructuredSpecReadService(
                    unit_of_work=runtime.unit_of_work, access=read_access,
                    license_guard=license_guard, authorization=authorization,
                    specs=SqlAlchemyStructuredSpecReadRepository())),
            ("plan", "PLN-02-WBS"): PlanWbsTraceOwner(
                PlanWbsTraceReadService(
                    access=read_access, license_guard=license_guard,
                    authorization=authorization,
                    repository=SqlAlchemyPlanWbsTraceReadRepository())),
        }
        proofs = TraceTargetProofService(owners)
        graph = TraceBoundedGraphService(
            unit_of_work=runtime.unit_of_work,
            sessions=read_access, projects=authorization,
            license_guard=license_guard, proofs=proofs,
            repository=SqlAlchemyTraceAdjacencyRepository())
        pages = TraceGraphPageService(
            graph=graph, cursor_codec=cursors,
            clock=lambda: datetime.now(timezone.utc))
        public = TracePublicGraphReadService(
            unit_of_work=runtime.unit_of_work,
            roots=TracePublicEdgeResolver({
                resource_type: owner for (_, resource_type), owner in owners.items()}),
            pages=pages)
        return create_trace_graph_router(
            sessions=sessions, origins=origins, graphs=public)
    except Exception:
        raise ProductionTraceGraphStartupError() from None
