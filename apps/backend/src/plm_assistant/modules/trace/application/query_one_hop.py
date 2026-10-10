"""Bounded internal Trace adjacency, with current authorization at every endpoint."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction, ProjectAuthorizationError,
)

from .target_proof import TraceProofQuery, TraceTargetProofError, TraceTargetProofService
from ..domain.link_shape import TraceEdgeShape, TraceVersionRef


class TraceQueryError(RuntimeError):
    def __init__(self, code: str = "TRACE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceOneHopQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    root: TraceVersionRef
    direction: str
    relation_type: str | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class TraceAdjacency:
    trace_link_id: uuid.UUID
    edge: TraceEdgeShape


@dataclass(frozen=True, slots=True)
class TraceOneHopResult:
    root: TraceVersionRef
    links: tuple[TraceAdjacency, ...]
    truncated: bool


class TraceReadSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class TraceReadProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str) -> AuthorizedProjectAction: ...


class TraceReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class TraceAdjacencyPort(Protocol):
    def adjacent(self, transaction: object, *, project_id: uuid.UUID,
                 root: TraceVersionRef, direction: str, relation_type: str | None,
                 limit: int) -> tuple[TraceAdjacency, ...]: ...


class TraceOneHopService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 sessions: TraceReadSessionPort, projects: TraceReadProjectPort,
                 license_guard: TraceReadLicensePort, proofs: TraceTargetProofService,
                 repository: TraceAdjacencyPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(v is None for v in (unit_of_work, sessions, projects,
                                   license_guard, proofs, repository)):
            raise ValueError("Trace read dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._proofs, self._repository = license_guard, proofs, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def query(self, query: TraceOneHopQuery) -> TraceOneHopResult:
        if (type(query) is not TraceOneHopQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or any(type(v) is not uuid.UUID or v.int == 0 for v in
                       (query.trace_id, query.project_id))
                or type(query.root) is not TraceVersionRef
                or query.root.scope == "PROJECT" and query.root.project_id != query.project_id
                or query.direction not in ("UPSTREAM", "DOWNSTREAM")
                or query.relation_type is not None
                and query.relation_type not in (
                    "DERIVED_FROM", "REFINES", "IMPLEMENTS", "VALIDATES",
                    "GENERATED_FROM", "REFERENCES_CAPABILITY", "SUPERSEDES")
                or type(query.limit) is not int or not 1 <= query.limit <= 100):
            raise TraceQueryError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise TraceQueryError()
                actor = self._sessions.authenticated_user(
                    tx, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise TraceQueryError("AUTH_ACCESS_DENIED")
                project = self._projects.require_in_transaction(
                    tx, user_id=actor, project_id=query.project_id,
                    operation="TRACE_GRAPH_READ",
                )
                if (type(project) is not AuthorizedProjectAction
                        or project.user_id != actor or project.project_id != query.project_id
                        or project.operation != "TRACE_GRAPH_READ"):
                    raise TraceQueryError("RESOURCE_NOT_FOUND")
                proof_query = TraceProofQuery(query.session_token, query.trace_id)
                self._proofs.prove_ref(tx, proof_query, query.root)
                candidates = self._repository.adjacent(
                    tx, project_id=query.project_id, root=query.root,
                    direction=query.direction, relation_type=query.relation_type,
                    limit=query.limit + 1,
                )
                if type(candidates) is not tuple or len(candidates) > query.limit + 1:
                    raise TraceQueryError()
                visible: list[TraceAdjacency] = []
                truncated = len(candidates) > query.limit
                for item in candidates[:query.limit]:
                    if (type(item) is not TraceAdjacency
                            or type(item.trace_link_id) is not uuid.UUID
                            or item.trace_link_id.int == 0
                            or type(item.edge) is not TraceEdgeShape
                            or item.edge.scope != "PROJECT"
                            or item.edge.project_id != query.project_id
                            or (item.edge.target if query.direction == "UPSTREAM"
                                else item.edge.source) != query.root
                            or query.relation_type is not None
                            and item.edge.relation_type != query.relation_type):
                        raise TraceQueryError()
                    try:
                        self._proofs.prove_edge(tx, proof_query, item.edge)
                    except TraceTargetProofError as exc:
                        if exc.code == "RESOURCE_NOT_FOUND":
                            truncated = True
                            continue
                        raise
                    visible.append(item)
                return TraceOneHopResult(query.root, tuple(visible), truncated)
        except TraceQueryError:
            raise
        except ProjectAuthorizationError:
            raise TraceQueryError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise TraceQueryError("LICENSE_OPERATION_DENIED") from None
        except TraceTargetProofError as exc:
            if exc.code in ("RESOURCE_NOT_FOUND", "LICENSE_OPERATION_DENIED"):
                raise TraceQueryError(exc.code) from None
            raise TraceQueryError() from None
        except Exception:
            raise TraceQueryError() from None
