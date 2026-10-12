"""Composition bridge from Trace fixed refs to Requirement-owned authorization."""

from __future__ import annotations

import uuid

from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadError, RequirementVersionReadQuery,
    RequirementVersionReadService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof, TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class RequirementVersionTraceOwner:
    def __init__(self, requirements: RequirementVersionReadService) -> None:
        if requirements is None:
            raise ValueError("Requirement read service is required")
        self._requirements = requirements

    def resolve(self, transaction: object, query: TraceProofQuery,
                path_project_id: uuid.UUID,
                ref: TraceResourceVersionRef) -> TraceVersionRef:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(path_project_id) is not uuid.UUID or path_project_id.int == 0
                or type(ref) is not TraceResourceVersionRef
                or ref.resource_type != "REQ-03"):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, path_project_id,
                   ref.resource_id, ref.version_id)
        return TraceVersionRef("requirement", "REQ-03", ref.resource_id,
                               ref.version_id, "PROJECT", path_project_id)

    def prove(self, transaction: object, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(ref) is not TraceVersionRef
                or (ref.owner_module, ref.object_type) != ("requirement", "REQ-03")
                or ref.scope != "PROJECT" or ref.project_id is None):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, ref.project_id,
                   ref.object_id, ref.version_id)
        return TraceTargetProof(ref)

    def _read(self, transaction: object, query: TraceProofQuery,
              project_id: uuid.UUID, requirement_id: uuid.UUID,
              version_id: uuid.UUID) -> None:
        try:
            self._requirements.get_version_for_trace(
                transaction,
                RequirementVersionReadQuery(query.session_token, query.trace_id,
                                            project_id),
                requirement_id=requirement_id,
                requirement_version_id=version_id,
            )
        except RequirementVersionReadError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceTargetProofError("LICENSE_OPERATION_DENIED") from None
            if exc.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"):
                raise TraceTargetProofError("RESOURCE_NOT_FOUND") from None
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
