"""Fail-closed owner-port authorization for fixed Trace endpoints."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from plm_assistant.modules.trace.domain.link_shape import (
    TraceEdgeShape, TraceShapeError, TraceVersionRef,
)


class TraceTargetProofError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceProofQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TraceResourceVersionRef:
    """The frozen public three-field reference before an Owner resolves scope."""

    resource_type: str
    resource_id: uuid.UUID
    version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TraceTargetProof:
    ref: TraceVersionRef


class TraceTargetOwnerPort(Protocol):
    def prove(self, transaction: object, query: TraceProofQuery,
              ref: TraceVersionRef) -> TraceTargetProof: ...


class TracePublicRefOwnerPort(Protocol):
    def resolve(self, transaction: object, query: TraceProofQuery,
                path_project_id: uuid.UUID,
                ref: TraceResourceVersionRef) -> TraceVersionRef: ...


class TracePublicEdgeResolver:
    """Resolve frozen three-field refs through explicitly registered owners."""

    def __init__(self, owners: Mapping[str, TracePublicRefOwnerPort]) -> None:
        if type(owners) is not dict or any(
            type(resource_type) is not str or not resource_type or owner is None
            for resource_type, owner in owners.items()
        ):
            raise ValueError("Trace public owners must be explicitly registered")
        self._owners = dict(owners)

    def resolve_edge(self, transaction: object, query: TraceProofQuery,
                     project_id: uuid.UUID, source: TraceResourceVersionRef,
                     target: TraceResourceVersionRef,
                     relation_type: str) -> TraceEdgeShape:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or any(type(ref) is not TraceResourceVersionRef
                       or type(ref.resource_type) is not str
                       or type(ref.resource_id) is not uuid.UUID
                       or ref.resource_id.int == 0
                       or type(ref.version_id) is not uuid.UUID
                       or ref.version_id.int == 0 for ref in (source, target))
                or type(relation_type) is not str):
            raise TraceTargetProofError("VALIDATION_FAILED")
        refs = []
        for public_ref in (source, target):
            owner = self._owners.get(public_ref.resource_type)
            if owner is None:
                raise TraceTargetProofError("RESOURCE_NOT_FOUND")
            try:
                resolved = owner.resolve(transaction, query, project_id, public_ref)
            except TraceTargetProofError:
                raise
            except Exception:
                raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
            if (type(resolved) is not TraceVersionRef
                    or resolved.object_type != public_ref.resource_type
                    or resolved.object_id != public_ref.resource_id
                    or resolved.version_id != public_ref.version_id):
                raise TraceTargetProofError("TRACE_UNAVAILABLE")
            refs.append(resolved)
        try:
            edge = TraceEdgeShape(refs[0], refs[1], relation_type)
        except TraceShapeError:
            raise TraceTargetProofError("VALIDATION_FAILED") from None
        if edge.scope != "PROJECT" or edge.project_id != project_id:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        return edge


class TraceTargetProofService:
    def __init__(self, owners: Mapping[tuple[str, str], TraceTargetOwnerPort]) -> None:
        if type(owners) is not dict or any(
            type(key) is not tuple or len(key) != 2 or provider is None
            for key, provider in owners.items()
        ):
            raise ValueError("Trace target owners must be explicitly registered")
        self._owners = dict(owners)

    def prove_edge(self, transaction: object, query: TraceProofQuery,
                   edge: TraceEdgeShape) -> tuple[TraceTargetProof, TraceTargetProof]:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(edge) is not TraceEdgeShape):
            raise TraceTargetProofError("VALIDATION_FAILED")
        return (self._prove_one(transaction, query, edge.source),
                self._prove_one(transaction, query, edge.target))

    def prove_ref(self, transaction: object, query: TraceProofQuery,
                  ref: TraceVersionRef) -> TraceTargetProof:
        if (transaction is None or type(query) is not TraceProofQuery
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or type(ref) is not TraceVersionRef):
            raise TraceTargetProofError("VALIDATION_FAILED")
        return self._prove_one(transaction, query, ref)

    def _prove_one(self, transaction: object, query: TraceProofQuery,
                   ref: TraceVersionRef) -> TraceTargetProof:
        provider = self._owners.get((ref.owner_module, ref.object_type))
        if provider is None:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        try:
            proof = provider.prove(transaction, query, ref)
        except TraceTargetProofError:
            raise
        except Exception:
            raise TraceTargetProofError("TRACE_UNAVAILABLE") from None
        if type(proof) is not TraceTargetProof or proof.ref != ref:
            raise TraceTargetProofError("TRACE_UNAVAILABLE")
        return proof
