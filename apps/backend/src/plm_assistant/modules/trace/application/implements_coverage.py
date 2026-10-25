"""Current exact Requirement IMPLEMENTS coverage for one fixed Solution version."""

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
    target: TraceVersionRef
    requirement_refs: tuple[TraceVersionRef, ...]
    trace_link_ids: tuple[uuid.UUID, ...]


class TraceImplementsRepositoryPort(Protocol):
    def active_for_target(self, transaction: object, *,
                          project_id: uuid.UUID,
                          target: TraceVersionRef,
                          limit: int) -> tuple[TraceAdjacency, ...]: ...


class TraceImplementsCoverageService:
    def __init__(self, *, repository: TraceImplementsRepositoryPort,
                 owners: TraceTargetProofService) -> None:
        if repository is None or owners is None:
            raise ValueError("Trace IMPLEMENTS dependencies required")
        self._repository, self._owners = repository, owners

    def prove(self, transaction: object, *, query: TraceProofQuery,
              target: TraceVersionRef,
              requirement_refs: tuple[TraceVersionRef, ...]) -> TraceImplementsCoverageProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(target) is not TraceVersionRef
                or target.owner_module != "solution"
                or target.object_type not in ("SOL-05", "SOL-06")
                or target.scope != "PROJECT"
                or type(requirement_refs) is not tuple
                or not 1 <= len(requirement_refs) <= 500
                or any(type(ref) is not TraceVersionRef
                       or (ref.owner_module, ref.object_type, ref.scope,
                           ref.project_id) != (
                               "requirement", "REQ-03", "PROJECT", target.project_id)
                       for ref in requirement_refs)
                or len({ref.object_id for ref in requirement_refs})
                != len(requirement_refs)
                or len({ref.version_id for ref in requirement_refs})
                != len(requirement_refs)):
            raise TraceImplementsCoverageError()
        try:
            self._owners.prove_ref(transaction, query, target)
            rows = self._repository.active_for_target(
                transaction, project_id=target.project_id,
                target=target, limit=501,
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
                        or item.edge.project_id != target.project_id
                        or item.edge.relation_type != "IMPLEMENTS"
                        or item.edge.target != target
                        or item.edge.source not in expected
                        or item.edge.source in seen):
                    raise TraceImplementsCoverageError()
                self._owners.prove_edge(transaction, query, item.edge)
                seen.add(item.edge.source)
                link_ids.add(item.trace_link_id)
            if seen != expected:
                raise TraceImplementsCoverageError()
            return TraceImplementsCoverageProof(
                target, requirement_refs,
                tuple(item.trace_link_id for item in rows),
            )
        except TraceImplementsCoverageError:
            raise
        except TraceTargetProofError as exc:
            if exc.code == "LICENSE_OPERATION_DENIED":
                raise TraceImplementsCoverageError("LICENSE_OPERATION_DENIED") from None
            if exc.code == "RESOURCE_NOT_FOUND":
                raise TraceImplementsCoverageError() from None
            raise TraceImplementsCoverageError("TRACE_UNAVAILABLE") from None
        except Exception:
            raise TraceImplementsCoverageError("TRACE_UNAVAILABLE") from None
