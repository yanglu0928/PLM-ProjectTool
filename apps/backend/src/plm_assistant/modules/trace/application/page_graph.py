"""Authenticated continuation over a freshly re-proved bounded Trace graph."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .query_bounded_graph import TraceBoundedGraph, TraceBoundedGraphQuery
from .query_one_hop import TraceAdjacency, TraceQueryError
from ..domain.link_shape import TraceVersionRef


_TOKEN = re.compile(r"g1\.[A-Za-z0-9_-]{1,2048}\Z", re.ASCII)
_FAMILY = "plm-trace-graph-aesgcm-v1"
_TTL_SECONDS = 900


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _ref(ref: TraceVersionRef) -> dict[str, str | None]:
    return {
        "owner": ref.owner_module, "type": ref.object_type,
        "object": str(ref.object_id), "version": str(ref.version_id),
        "scope": ref.scope,
        "project": str(ref.project_id) if ref.project_id is not None else None,
    }


def _aad(query: TraceBoundedGraphQuery, page_size: int) -> bytes:
    if (type(query) is not TraceBoundedGraphQuery
            or type(query.session_token) is not bytes or len(query.session_token) != 32
            or type(query.root) is not TraceVersionRef
            or type(page_size) is not int or not 1 <= page_size <= 100):
        raise TraceQueryError("VALIDATION_FAILED")
    return _json({
        "family": _FAMILY, "v": 1,
        "session": hashlib.sha256(query.session_token).hexdigest(),
        "project": str(query.project_id), "root": _ref(query.root),
        "direction": query.direction, "relation": query.relation_type,
        "max_depth": query.max_depth, "max_nodes": query.max_nodes,
        "page_size": page_size,
    })


def _digest(graph: TraceBoundedGraph) -> str:
    if (type(graph) is not TraceBoundedGraph or type(graph.nodes) is not tuple
            or type(graph.links) is not tuple or type(graph.truncated) is not bool):
        raise TraceQueryError()
    return hashlib.sha256(_json({
        "root": _ref(graph.root), "nodes": [_ref(ref) for ref in graph.nodes],
        "links": [{"id": str(link.trace_link_id), "source": _ref(link.edge.source),
                   "target": _ref(link.edge.target), "relation": link.edge.relation_type}
                  for link in graph.links],
        "truncated": graph.truncated,
    })).hexdigest()


class TraceGraphCursorCodec:
    def __init__(self, key: bytes) -> None:
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("dedicated 32-byte Trace graph cursor key required")
        self._cipher = AESGCM(key)

    def encode(self, *, query: TraceBoundedGraphQuery, page_size: int,
               next_index: int, graph_digest: str, now: datetime) -> str:
        if (type(next_index) is not int or not 0 < next_index <= 2000
                or type(graph_digest) is not str
                or re.fullmatch(r"[0-9a-f]{64}", graph_digest) is None
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise TraceQueryError("VALIDATION_FAILED")
        aad = _aad(query, page_size)
        payload = _json({"v": 1, "next": next_index, "digest": graph_digest,
                         "issued": int(now.timestamp())})
        nonce = os.urandom(12)
        return "g1." + _b64(nonce + self._cipher.encrypt(nonce, payload, aad))

    def decode(self, token: str, *, query: TraceBoundedGraphQuery,
               page_size: int, now: datetime) -> tuple[int, str]:
        try:
            aad = _aad(query, page_size)
            if (type(token) is not str or _TOKEN.fullmatch(token) is None
                    or type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise ValueError()
            encoded = token[3:]
            packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if len(packed) < 29 or _b64(packed) != encoded:
                raise ValueError()
            raw = self._cipher.decrypt(packed[:12], packed[12:], aad)
            value = json.loads(raw.decode("ascii"))
            if (type(value) is not dict or set(value) != {"v", "next", "digest", "issued"}
                    or type(value["v"]) is not int or value["v"] != 1
                    or type(value["next"]) is not int or not 0 < value["next"] <= 2000
                    or type(value["digest"]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", value["digest"]) is None
                    or type(value["issued"]) is not int or _json(value) != raw):
                raise ValueError()
            age = int(now.timestamp()) - value["issued"]
            if not -30 <= age <= _TTL_SECONDS:
                raise ValueError()
            return value["next"], value["digest"]
        except Exception:
            raise TraceQueryError("VALIDATION_FAILED") from None


@dataclass(frozen=True, slots=True)
class TraceGraphPage:
    root: TraceVersionRef
    nodes: tuple[TraceVersionRef, ...]
    links: tuple[TraceAdjacency, ...]
    next_cursor: str | None
    truncated: bool


class BoundedGraphPort(Protocol):
    def query(self, query: TraceBoundedGraphQuery) -> TraceBoundedGraph: ...


class TraceGraphPageService:
    def __init__(self, *, graph: BoundedGraphPort, cursor_codec: TraceGraphCursorCodec,
                 clock) -> None:
        if graph is None or type(cursor_codec) is not TraceGraphCursorCodec or clock is None:
            raise ValueError("Trace graph paging dependencies required")
        self._graph, self._codec, self._clock = graph, cursor_codec, clock

    def query_page(self, query: TraceBoundedGraphQuery, *, page_size: int,
                   cursor: str | None = None) -> TraceGraphPage:
        aad = _aad(query, page_size)
        if not aad or cursor is not None and type(cursor) is not str:
            raise TraceQueryError("VALIDATION_FAILED")
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise TraceQueryError()
        before = self._codec.decode(cursor, query=query, page_size=page_size,
                                    now=now) if cursor is not None else None
        graph = self._graph.query(query)  # Current authorization and graph, every page.
        digest = _digest(graph)
        if graph.root != query.root or not graph.nodes or graph.nodes[0] != query.root:
            raise TraceQueryError()
        start = 0 if before is None else before[0]
        if before is not None and (before[1] != digest or start >= len(graph.links)):
            raise TraceQueryError("TRACE_CURSOR_STALE")
        end = min(start + page_size, len(graph.links))
        links = graph.links[start:end]
        nodes = [query.root]
        seen = {query.root}
        for link in links:
            for ref in (link.edge.source, link.edge.target):
                if ref not in seen:
                    seen.add(ref)
                    nodes.append(ref)
        next_cursor = (self._codec.encode(
            query=query, page_size=page_size, next_index=end,
            graph_digest=digest, now=now,
        ) if end < len(graph.links) else None)
        return TraceGraphPage(query.root, tuple(nodes), links,
                              next_cursor, graph.truncated)
