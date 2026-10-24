import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from plm_assistant.modules.trace.application.page_graph import (
    TraceGraphCursorCodec, TraceGraphPageService,
)
from plm_assistant.modules.trace.application.query_bounded_graph import (
    TraceBoundedGraph, TraceBoundedGraphQuery,
)
from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency, TraceQueryError
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class Graph:
    def __init__(self, value):
        self.value = value
        self.calls = 0
        self.error = None

    def query(self, query):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.value


class TraceGraphPageTests(unittest.TestCase):
    def setUp(self):
        project_id = uuid4()
        self.refs = [TraceVersionRef("document", "DOC-02", uuid4(), uuid4(),
                                     "PROJECT", project_id) for _ in range(4)]
        self.query = TraceBoundedGraphQuery(
            b"s" * 32, uuid4(), project_id, self.refs[0], "DOWNSTREAM",
        )
        self.links = tuple(TraceAdjacency(
            uuid4(), TraceEdgeShape(self.refs[i], self.refs[i+1], "DERIVED_FROM"),
        ) for i in range(3))
        self.graph = Graph(TraceBoundedGraph(self.refs[0], tuple(self.refs),
                                             self.links, False))
        self.now = datetime(2026, 10, 2, tzinfo=timezone.utc)
        self.codec = TraceGraphCursorCodec(b"k" * 32)
        self.service = TraceGraphPageService(
            graph=self.graph, cursor_codec=self.codec, clock=lambda: self.now,
        )

    def test_three_pages_reprove_graph_and_return_only_page_nodes(self):
        first = self.service.query_page(self.query, page_size=1)
        self.assertEqual(first.links, (self.links[0],))
        self.assertEqual(first.nodes, (self.refs[0], self.refs[1]))
        self.assertIsNotNone(first.next_cursor)
        self.assertNotIn(str(self.refs[1].object_id), first.next_cursor)
        second = self.service.query_page(self.query, page_size=1,
                                         cursor=first.next_cursor)
        self.assertEqual(second.links, (self.links[1],))
        self.assertEqual(second.nodes, (self.refs[0], self.refs[1], self.refs[2]))
        third = self.service.query_page(self.query, page_size=1,
                                        cursor=second.next_cursor)
        self.assertEqual(third.links, (self.links[2],))
        self.assertIsNone(third.next_cursor)
        self.assertEqual(self.graph.calls, 3)

    def test_cursor_bound_to_session_project_query_and_page_size(self):
        token = self.service.query_page(self.query, page_size=1).next_cursor
        for changed, size in (
                (replace(self.query, session_token=b"x" * 32), 1),
                (replace(self.query, project_id=uuid4()), 1),
                (replace(self.query, direction="UPSTREAM"), 1),
                (replace(self.query, max_depth=2), 1),
                (replace(self.query, relation_type="REFINES"), 1),
                (self.query, 2)):
            with self.subTest(changed=changed, size=size), self.assertRaises(TraceQueryError):
                self.service.query_page(changed, page_size=size, cursor=token)
        self.assertEqual(self.graph.calls, 1)

    def test_tampered_or_expired_cursor_rejected_before_graph_read(self):
        token = self.service.query_page(self.query, page_size=1).next_cursor
        other_key = TraceGraphPageService(
            graph=self.graph, cursor_codec=TraceGraphCursorCodec(b"x" * 32),
            clock=lambda: self.now,
        )
        with self.assertRaises(TraceQueryError):
            other_key.query_page(self.query, page_size=1, cursor=token)
        for bad in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                    "g1.invalid!", "", None):
            if bad is None:
                continue
            with self.assertRaises(TraceQueryError):
                self.service.query_page(self.query, page_size=1, cursor=bad)
        self.now += timedelta(minutes=16)
        with self.assertRaises(TraceQueryError):
            self.service.query_page(self.query, page_size=1, cursor=token)
        self.assertEqual(self.graph.calls, 1)

    def test_graph_or_permission_change_invalidates_old_cursor(self):
        token = self.service.query_page(self.query, page_size=1).next_cursor
        self.graph.value = replace(self.graph.value,
                                   links=self.links[:2], nodes=tuple(self.refs[:3]))
        with self.assertRaises(TraceQueryError) as caught:
            self.service.query_page(self.query, page_size=1, cursor=token)
        self.assertEqual(caught.exception.code, "TRACE_CURSOR_STALE")
        self.graph.error = TraceQueryError("RESOURCE_NOT_FOUND")
        with self.assertRaises(TraceQueryError) as caught:
            self.service.query_page(self.query, page_size=1, cursor=token)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_truncated_graph_remains_explicit_on_final_page(self):
        self.graph.value = replace(self.graph.value, truncated=True)
        page = self.service.query_page(self.query, page_size=2)
        self.assertTrue(page.truncated)
        final = self.service.query_page(self.query, page_size=2,
                                        cursor=page.next_cursor)
        self.assertTrue(final.truncated)
        self.assertIsNone(final.next_cursor)

    def test_invalid_inputs_and_key(self):
        with self.assertRaises(ValueError):
            TraceGraphCursorCodec(b"short")
        for size in (0, 101, True):
            with self.assertRaises(TraceQueryError):
                self.service.query_page(self.query, page_size=size)
        self.assertEqual(self.graph.calls, 0)


if __name__ == "__main__":
    unittest.main()
