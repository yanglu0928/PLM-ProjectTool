"""Resolve a public fixed root, then re-prove every graph page in a new transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .page_graph import TraceGraphPage
from .query_bounded_graph import TraceBoundedGraphQuery
from .query_one_hop import TraceQueryError
from .target_proof import (
    TraceProofQuery, TracePublicEdgeResolver, TraceResourceVersionRef,
    TraceTargetProofError,
)


@dataclass(frozen=True, slots=True)
class TracePublicGraphQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    root: TraceResourceVersionRef
    direction: str
    relation_type: str | None = None
    max_depth: int = 3
    max_nodes: int = 100
    page_size: int = 100
    cursor: str | None = None


class PagePort(Protocol):
    def query_page(self, query: TraceBoundedGraphQuery, *, page_size: int,
                   cursor: str | None = None) -> TraceGraphPage: ...


class TracePublicGraphReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 roots: TracePublicEdgeResolver, pages: PagePort) -> None:
        if unit_of_work is None or roots is None or pages is None:
            raise ValueError("Trace public graph dependencies required")
        self._uow, self._roots, self._pages = unit_of_work, roots, pages

    def query_page(self, query: TracePublicGraphQuery) -> TraceGraphPage:
        if (type(query) is not TracePublicGraphQuery
                or type(query.session_token) is not bytes
                or len(query.session_token) != 32
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in (query.trace_id, query.project_id))
                or type(query.root) is not TraceResourceVersionRef
                or query.direction not in ("UPSTREAM", "DOWNSTREAM")
                or query.relation_type is not None and query.relation_type not in (
                    "DERIVED_FROM", "REFINES", "IMPLEMENTS", "VALIDATES",
                    "GENERATED_FROM", "REFERENCES_CAPABILITY", "SUPERSEDES")
                or type(query.max_depth) is not int or not 1 <= query.max_depth <= 10
                or type(query.max_nodes) is not int or not 1 <= query.max_nodes <= 500
                or type(query.page_size) is not int or not 1 <= query.page_size <= 100
                or query.cursor is not None and type(query.cursor) is not str):
            raise TraceQueryError("VALIDATION_FAILED")
        try:
            with self._uow() as transaction:
                root = self._roots.resolve_ref(
                    transaction, TraceProofQuery(query.session_token, query.trace_id),
                    query.project_id, query.root)
            fixed = TraceBoundedGraphQuery(
                query.session_token, query.trace_id, query.project_id,
                root, query.direction, query.relation_type,
                query.max_depth, query.max_nodes)
            page = self._pages.query_page(
                fixed, page_size=query.page_size, cursor=query.cursor)
            if type(page) is not TraceGraphPage or page.root != root:
                raise TraceQueryError()
            return page
        except TraceQueryError:
            raise
        except TraceTargetProofError as error:
            if error.code in ("RESOURCE_NOT_FOUND", "LICENSE_OPERATION_DENIED"):
                raise TraceQueryError(error.code) from None
            if error.code == "VALIDATION_FAILED":
                raise TraceQueryError("VALIDATION_FAILED") from None
            raise TraceQueryError() from None
        except Exception:
            raise TraceQueryError() from None
