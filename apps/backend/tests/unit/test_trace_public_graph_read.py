from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.trace.application.page_graph import TraceGraphPage
from plm_assistant.modules.trace.application.query_one_hop import TraceQueryError
from plm_assistant.modules.trace.application.read_public_graph import (
    TracePublicGraphQuery, TracePublicGraphReadService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TracePublicEdgeResolver, TraceResourceVersionRef, TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Owner:
    error = None
    project = None
    calls = 0

    def resolve(self, tx, query, project_id, ref):
        self.calls += 1
        if self.error:
            raise TraceTargetProofError(self.error)
        return TraceVersionRef("plan", "PLN-02-WBS", ref.resource_id,
                               ref.version_id, "PROJECT", self.project or project_id)


class Pages:
    error = None
    calls = 0

    def query_page(self, query, *, page_size, cursor=None):
        self.calls += 1
        self.query, self.size, self.cursor = query, page_size, cursor
        if self.error:
            raise TraceQueryError(self.error)
        return TraceGraphPage(query.root, (query.root,), (), None, False)


class TracePublicGraphReadTests(unittest.TestCase):
    def setUp(self):
        self.project, self.item, self.version = (uuid.uuid4() for _ in range(3))
        self.owner, self.pages = Owner(), Pages()
        self.service = TracePublicGraphReadService(
            unit_of_work=Tx,
            roots=TracePublicEdgeResolver({"PLN-02-WBS": self.owner}),
            pages=self.pages)
        self.query = TracePublicGraphQuery(
            b"s" * 32, uuid.uuid4(), self.project,
            TraceResourceVersionRef("PLN-02-WBS", self.item, self.version),
            "UPSTREAM", page_size=25)

    def rejects(self, code, query):
        with self.assertRaises(TraceQueryError) as caught:
            self.service.query_page(query)
        self.assertEqual(caught.exception.code, code)

    def test_fixed_root_and_page_query(self):
        page = self.service.query_page(self.query)
        self.assertEqual(page.root.object_id, self.item)
        self.assertEqual(page.root.version_id, self.version)
        self.assertEqual(self.pages.query.direction, "UPSTREAM")
        self.assertEqual(self.pages.query.project_id, self.project)
        self.assertEqual(self.pages.size, 25)

    def test_bad_input_and_unregistered_owner_fail_before_page(self):
        self.rejects("VALIDATION_FAILED", replace(self.query, max_depth=11))
        self.rejects("VALIDATION_FAILED", replace(self.query, page_size=True))
        self.rejects("RESOURCE_NOT_FOUND", replace(
            self.query, root=replace(self.query.root, resource_type="PLN-02")))
        self.assertEqual(self.pages.calls, 0)

    def test_owner_scope_and_errors_fail_closed(self):
        self.owner.project = uuid.uuid4()
        self.rejects("TRACE_UNAVAILABLE", self.query)
        self.owner.project = None
        for code, expected in (
            ("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
            ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
            ("PLAN_UNAVAILABLE", "TRACE_UNAVAILABLE"),
        ):
            with self.subTest(code=code):
                self.owner.error = code
                self.rejects(expected, self.query)
        self.assertEqual(self.pages.calls, 0)

    def test_page_error_is_not_downgraded(self):
        self.pages.error = "TRACE_CURSOR_STALE"
        self.rejects("TRACE_CURSOR_STALE", self.query)


if __name__ == "__main__":
    unittest.main()
