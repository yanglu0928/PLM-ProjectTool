"""Current, exact IMPLEMENTS coverage for one fixed SectionVersion."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from .query_one_hop import TraceAdjacency
from .target_proof import (
    TraceProofQuery, TraceTargetProofError, TraceTargetProofService,
)
from ..domain.link_shape import TraceEdgeShape, TraceVersionRef


class TraceImplementsCoverageError(RuntimeError):
    def __init__(self, code: str = "TRACE_COVERAGE_REQUIRED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceImplementsCoverageProof:
    section: TraceVersionRef
    requirement_refs: tuple[TraceVersionRef, ...]
    trace_link_ids: tuple[uuid.UUID, ...]


class TraceImplementsRepositoryPort(Protocol):
    def active_for_section(self, transaction: object, *,
                           project_id: uuid.UUID,
                           section: TraceVersionRef,
                           limit: int) -> tuple[TraceAdjacency, ...]: ...


class TraceImplementsCoverageService:
    def __init__(self, *, repository: TraceImplementsRepositoryPort,
                 owners: TraceTargetProofService) -> None:
        if repository is None or owners is None:
            raise ValueError("Trace IMPLEMENTS dependencies required")
        self._repository, self._owners = repository, owners

    def prove(self, transaction: object, *, query: TraceProofQuery,
              section: TraceVersionRef,
              requirement_refs: tuple[TraceVersionRef, ...]) -> TraceImplementsCoverageProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(section) is not TraceVersionRef
                or (section.owner_module, section.object_type, section.scope)
                != ("solution", "SOL-05", "PROJECT")
                or type(requirement_refs) is not tuple
                or not 1 <= len(requirement_refs) <= 500
                or any(type(ref) is not TraceVersionRef
                       or (ref.owner_module, ref.object_type, ref.scope,
                           ref.project_id) != (
                               "requirement", "REQ-03", "PROJECT", section.project_id)
                       for ref in requirement_refs)
                or len({ref.object_id for ref in requirement_refs})
                != len(requirement_refs)
                or len({ref.version_id for ref in requirement_refs})
                != len(requirement_refs)):
            raise TraceImplementsCoverageError()
        try:
            self._owners.prove_ref(transaction, query, section)
            rows = self._repository.active_for_section(
                transaction, project_id=section.project_id,
                section=section, limit=501,
            )
            if (type(rows) is not tuple or len(rows) != len(requirement_refs)
                    or len(rows) > 500):
                raise TraceImplementsCoverageError()
            expected = set(requirement_refs)
            seen: set[TraceVersionRef] = set()
            link_ids: set[uuid.UUID] = set()
            for item in rows:
                if (type(item) is not TraceAdjacency
                        or type(item.trace_link_id) is not uuid.UUID
                        or item.trace_link_id.int == 0
                        or item.trace_link_id in link_ids
                        or type(item.edge) is not TraceEdgeShape
                        or item.edge.scope != "PROJECT"
                        or item.edge.project_id != section.project_id
                        or item.edge.relation_type != "IMPLEMENTS"
                        or item.edge.target != section
                        or item.edge.source not in expected
                        or item.edge.source in seen):
                    raise TraceImplementsCoverageError()
                self._owners.prove_edge(transaction, query, item.edge)
                seen.add(item.edge.source)
                link_ids.add(item.trace_link_id)
            if seen != expected:
                raise TraceImplementsCoverageError()
            return TraceImplementsCoverageProof(
                section, requirement_refs,
                tuple(item.trace_link_id for item in rows),
            )
        except TraceImplementsCoverageError:
            raise
        except TraceTargetProofError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceImplementsCoverageError("LICENSE_OPERATION_DENIED") from None
            raise TraceImplementsCoverageError() from None
        except Exception:
            raise TraceImplementsCoverageError("TRACE_UNAVAILABLE") from None
