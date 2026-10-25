from __future__ import annotations

import unittest

from plm_assistant.entrypoints.windows_trace_graph import (
    ProductionTraceGraphStartupError, create_windows_trace_graph_router,
)
from plm_assistant.modules.trace.application.page_graph import TraceGraphCursorCodec


class Runtime:
    def unit_of_work(self):
        raise AssertionError("factory must not query database")


class WindowsTraceGraphFactoryTests(unittest.TestCase):
    def test_explicit_router_with_both_frozen_operations(self):
        router = create_windows_trace_graph_router(
            runtime=Runtime(), sessions=object(), origins=object(),
            license_guard=object(), cursors=TraceGraphCursorCodec(b"t" * 32))
        self.assertEqual({route.operation_id for route in router.routes}, {
            "TRACE_GRAPH_UPSTREAM", "TRACE_GRAPH_DOWNSTREAM"})

    def test_missing_or_wrong_cursor_fails_closed(self):
        for value in (None, object()):
            with self.subTest(value=value), self.assertRaises(
                    ProductionTraceGraphStartupError):
                create_windows_trace_graph_router(
                    runtime=Runtime(), sessions=object(), origins=object(),
                    license_guard=object(), cursors=value)


if __name__ == "__main__":
    unittest.main()
