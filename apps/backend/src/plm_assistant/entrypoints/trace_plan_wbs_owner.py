"""Composition bridge from Trace fixed WBS refs to Plan-owned authorization."""

from __future__ import annotations

import uuid

from plm_assistant.modules.plan.application.read_wbs_for_trace import (
    PlanWbsTraceQuery, PlanWbsTraceReadError, PlanWbsTraceReadService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof, TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class PlanWbsTraceOwner:
    def __init__(self, wbs: PlanWbsTraceReadService) -> None:
        if wbs is None:
            raise ValueError("Plan WBS read service is required")
        self._wbs = wbs

    def resolve(self, transaction: object, query: TraceProofQuery,
                path_project_id: uuid.UUID,
                ref: TraceResourceVersionRef) -> TraceVersionRef:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(path_project_id) is not uuid.UUID or path_project_id.int == 0
                or type(ref) is not TraceResourceVersionRef
                or ref.resource_type != "PLN-02-WBS"):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, path_project_id,
                   ref.resource_id, ref.version_id)
        return TraceVersionRef("plan", "PLN-02-WBS", ref.resource_id,
                               ref.version_id, "PROJECT", path_project_id)

    def prove(self, transaction: object, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(ref) is not TraceVersionRef
                or (ref.owner_module, ref.object_type) != ("plan", "PLN-02-WBS")
                or ref.scope != "PROJECT" or ref.project_id is None):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, ref.project_id,
                   ref.object_id, ref.version_id)
        return TraceTargetProof(ref)

    def _read(self, transaction: object, query: TraceProofQuery,
              project_id: uuid.UUID, wbs_item_id: uuid.UUID,
              plan_version_id: uuid.UUID) -> None:
        try:
            self._wbs.get_for_trace(
                transaction,
                PlanWbsTraceQuery(query.session_token, query.trace_id, project_id),
                wbs_item_id=wbs_item_id, plan_version_id=plan_version_id,
            )
        except PlanWbsTraceReadError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceTargetProofError("LICENSE_OPERATION_DENIED") from None
            if exc.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"):
                raise TraceTargetProofError("RESOURCE_NOT_FOUND") from None
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
