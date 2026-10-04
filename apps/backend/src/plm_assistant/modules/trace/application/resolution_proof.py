"""Trace-owned proof for a Handover Action resolution link."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape

from .target_proof import (
    TraceProofQuery, TraceTargetProofError, TraceTargetProofService,
)


_HUMAN_TARGETS = frozenset({
    ("survey", "SRV-02"),
    ("survey", "SRV-05"),
    ("requirement", "REQ-03"),
})


class TraceResolutionProofError(RuntimeError):
    def __init__(self, code: str = "TRACE_RESOLUTION_REQUIRED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceResolutionProof:
    trace_link_id: uuid.UUID
    edge: TraceEdgeShape


class TraceResolutionRepositoryPort(Protocol):
    def active_project_edge(
        self, transaction: object, *, project_id: uuid.UUID,
        trace_link_id: uuid.UUID,
    ) -> TraceEdgeShape | None: ...


class TraceResolutionProofService:
    """Prove current endpoint facts without changing immutable Trace history."""

    def __init__(self, repository: TraceResolutionRepositoryPort,
                 owners: TraceTargetProofService) -> None:
        if repository is None or owners is None:
            raise ValueError("Trace resolution proof dependencies required")
        self._repository, self._owners = repository, owners

    def prove(
        self, transaction: object, *, session_token: bytes, trace_id: uuid.UUID,
        project_id: uuid.UUID, trace_link_id: uuid.UUID, source_kind: str,
        source_analysis_id: uuid.UUID | None,
        source_analysis_version_id: uuid.UUID | None, reason: str,
    ) -> TraceResolutionProof:
        if (transaction is None
                or type(session_token) is not bytes or len(session_token) != 32
                or type(trace_id) is not uuid.UUID or trace_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or type(trace_link_id) is not uuid.UUID or trace_link_id.int == 0
                or source_kind not in ("ANALYSIS_ITEM", "HUMAN")
                or type(reason) is not str or not 1 <= len(reason) <= 2000
                or reason != reason.strip()
                or (source_kind == "ANALYSIS_ITEM" and (
                    type(source_analysis_id) is not uuid.UUID
                    or source_analysis_id.int == 0
                    or type(source_analysis_version_id) is not uuid.UUID
                    or source_analysis_version_id.int == 0))
                or (source_kind == "HUMAN" and (
                    source_analysis_id is not None
                    or source_analysis_version_id is not None))):
            raise TraceResolutionProofError()
        edge = self._repository.active_project_edge(
            transaction, project_id=project_id, trace_link_id=trace_link_id,
        )
        if (type(edge) is not TraceEdgeShape or edge.scope != "PROJECT"
                or edge.project_id != project_id
                or edge.target.scope != "PROJECT"
                or edge.target.project_id != project_id):
            raise TraceResolutionProofError()
        if source_kind == "ANALYSIS_ITEM":
            if (edge.source.owner_module != "handover"
                    or edge.source.object_type != "HND-02"
                    or edge.source.object_id != source_analysis_id
                    or edge.source.version_id != source_analysis_version_id
                    or edge.source.scope != "PROJECT"
                    or edge.source.project_id != project_id):
                raise TraceResolutionProofError()
        elif ((edge.target.owner_module, edge.target.object_type)
              not in _HUMAN_TARGETS):
            raise TraceResolutionProofError()
        try:
            self._owners.prove_edge(
                transaction, TraceProofQuery(session_token, trace_id), edge,
            )
        except TraceTargetProofError:
            raise TraceResolutionProofError() from None
        return TraceResolutionProof(trace_link_id, edge)
