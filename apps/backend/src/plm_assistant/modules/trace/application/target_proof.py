"""Fail-closed owner-port authorization for fixed Trace endpoints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class TraceTargetProofError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceProofQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TraceTargetProof:
    ref: TraceVersionRef


class TraceTargetOwnerPort(Protocol):
    def prove(self, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof: ...


class TraceTargetProofService:
    def __init__(self, owners: Mapping[tuple[str, str], TraceTargetOwnerPort]) -> None:
        if type(owners) is not dict or any(
            type(key) is not tuple or len(key) != 2 or provider is None
            for key, provider in owners.items()
        ):
            raise ValueError("Trace target owners must be explicitly registered")
        self._owners = dict(owners)

    def prove_edge(self, query: TraceProofQuery,
                   edge: TraceEdgeShape) -> tuple[TraceTargetProof, TraceTargetProof]:
        if (type(query) is not TraceProofQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(edge) is not TraceEdgeShape):
            raise TraceTargetProofError("VALIDATION_FAILED")
        return self._prove_one(query, edge.source), self._prove_one(query, edge.target)

    def _prove_one(self, query: TraceProofQuery,
                   ref: TraceVersionRef) -> TraceTargetProof:
        provider = self._owners.get((ref.owner_module, ref.object_type))
        if provider is None:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        try:
            proof = provider.prove(query, ref)
        except TraceTargetProofError:
            raise
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        if type(proof) is not TraceTargetProof or proof.ref != ref:
            raise TraceTargetProofError("TRACE_UNAVAILABLE")
        return proof
