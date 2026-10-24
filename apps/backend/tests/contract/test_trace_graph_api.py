from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.trace.api.graph import create_trace_graph_router
from plm_assistant.modules.trace.application.page_graph import TraceGraphPage
from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency, TraceQueryError
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Graphs:
    error = None
    calls = 0
    forged = False

    def __init__(self, project, item, version):
        self.root = TraceVersionRef(
            "plan", "PLN-02-WBS", item, version, "PROJECT", project)
        self.source = TraceVersionRef(
            "requirement", "REQ-03", uuid.uuid4(), uuid.uuid4(),
            "PROJECT", project)

    def query_page(self, query):
        self.calls += 1
        self.query = query
        if self.error:
            raise TraceQueryError(self.error)
        edge = TraceEdgeShape(self.source, self.root, "DERIVED_FROM")
        root = replace(self.root, project_id=uuid.uuid4()) if self.forged else self.root
        return TraceGraphPage(root, (root, self.source),
                              (TraceAdjacency(uuid.uuid4(), edge),), None, False)


class TraceGraphApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.item, self.version = (uuid.uuid4() for _ in range(3))
        self.graphs = Graphs(self.project, self.item, self.version)
        router = create_trace_graph_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            graphs=self.graphs)
        self.client = TestClient(create_app(trace_graph_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.path = (f"/api/v1/projects/{self.project}/trace-graph:upstream"
                     f"?resource_type=PLN-02-WBS&resource_id={self.item}"
                     f"&version_id={self.version}")

    def test_default_closed_and_fixed_reverse_page(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual(data["root"]["resource_id"], str(self.item))
        self.assertEqual(data["root"]["version_id"], str(self.version))
        self.assertEqual(data["links"][0]["source"]["resource_type"], "REQ-03")
        self.assertEqual(data["links"][0]["target"]["resource_type"], "PLN-02-WBS")
        self.assertFalse(data["truncated"])
        self.assertIsNone(data["next_cursor"])
        self.assertEqual((self.graphs.query.direction, self.graphs.query.max_depth,
                          self.graphs.query.max_nodes, self.graphs.query.page_size),
                         ("UPSTREAM", 3, 100, 100))

    def test_direction_bounds_and_parameters(self):
        down = self.path.replace(":upstream", ":downstream")
        self.assertEqual(200, self.client.get(
            down + "&max_depth=10&max_nodes=500&page_size=1",
            headers=self.headers).status_code)
        self.assertEqual((self.graphs.query.direction, self.graphs.query.max_depth,
                          self.graphs.query.max_nodes, self.graphs.query.page_size),
                         ("DOWNSTREAM", 10, 500, 1))
        before = self.graphs.calls
        for suffix, expected in (
            ("&resource_id=" + str(self.item), 400),
            ("&scope=GLOBAL", 400),
            ("&max_depth=11", 422),
            ("&max_nodes=501", 422),
            ("&page_size=0", 422),
            ("&relation_type=", 422),
            ("&cursor=", 422),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(expected, self.client.get(
                    self.path + suffix, headers=self.headers).status_code)
        self.assertEqual(before, self.graphs.calls)

    def test_auth_and_safe_error_mapping(self):
        self.assertEqual(401, self.client.get(self.path).status_code)
        self.assertEqual(403, self.client.get(
            self.path, headers={**self.headers, "host": "evil.test"}).status_code)
        for code, expected in (
            ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("TRACE_CURSOR_STALE", 409),
            ("TRACE_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.graphs.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)
                self.assertNotIn("Traceback", response.text)

    def test_forged_page_fails_closed(self):
        self.graphs.forged = True
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(503, response.status_code)
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
