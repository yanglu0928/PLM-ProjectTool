"""Composition bridge from Trace fixed refs to Solution Section authorization."""

from __future__ import annotations

import uuid

from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionReadError, SectionVersionReadQuery, SectionVersionReadService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof, TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class SectionVersionTraceOwner:
    def __init__(self, sections: SectionVersionReadService) -> None:
        if sections is None:
            raise ValueError("Section read service is required")
        self._sections = sections

    def resolve(self, transaction: object, query: TraceProofQuery,
                path_project_id: uuid.UUID,
                ref: TraceResourceVersionRef) -> TraceVersionRef:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(path_project_id) is not uuid.UUID or path_project_id.int == 0
                or type(ref) is not TraceResourceVersionRef
                or ref.resource_type != "SOL-05"):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, path_project_id,
                   ref.resource_id, ref.version_id)
        return TraceVersionRef("solution", "SOL-05", ref.resource_id,
                               ref.version_id, "PROJECT", path_project_id)

    def prove(self, transaction: object, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(ref) is not TraceVersionRef
                or (ref.owner_module, ref.object_type) != ("solution", "SOL-05")
                or ref.scope != "PROJECT" or ref.project_id is None):
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        self._read(transaction, query, ref.project_id,
                   ref.object_id, ref.version_id)
        return TraceTargetProof(ref)

    def _read(self, transaction: object, query: TraceProofQuery,
              project_id: uuid.UUID, section_id: uuid.UUID,
              version_id: uuid.UUID) -> None:
        try:
            self._sections.get_for_trace(
                transaction,
                SectionVersionReadQuery(query.session_token, query.trace_id,
                                        project_id, section_id),
                version_id,
            )
        except SectionVersionReadError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceTargetProofError("LICENSE_OPERATION_DENIED") from None
            if exc.code in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"):
                raise TraceTargetProofError("RESOURCE_NOT_FOUND") from None
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
