import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.trace.application.query_bounded_graph import (
    TraceBoundedGraphQuery, TraceBoundedGraphService,
)
from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency, TraceQueryError
from plm_assistant.modules.trace.application.target_proof import (
    TraceTargetProof, TraceTargetProofError, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class Session:
    actor = uuid4()
    valid = True

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor if self.valid else None


class Project:
    role = "PROJECT_MANAGER"

    def actor_facts(self, *_args, **_kwargs):
        return ProjectActorFacts("ACTIVE", self.role)


class Guard:
    def require_valid(self, **_kwargs):
        return object()


class Owner:
    def __init__(self):
        self.denied = set()
        self.fail = False
        self.transactions = []

    def prove(self, tx, query, ref):
        self.transactions.append(tx)
        if self.fail:
            raise TraceTargetProofError("TRACE_UNAVAILABLE")
        if ref in self.denied:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        return TraceTargetProof(ref)


class Repository:
    def __init__(self):
        self.by_root = {}
        self.calls = []

    def adjacent(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return tuple(self.by_root.get(kwargs["root"], ()))[:kwargs["limit"]]


class TraceBoundedGraphTests(unittest.TestCase):
    def setUp(self):
        self.tx, self.session, self.project = Tx(), Session(), Project()
        self.owner, self.repo = Owner(), Repository()
        self.project_id = uuid4()
        self.refs = [TraceVersionRef("document", "DOC-02", uuid4(), uuid4(),
                                     "PROJECT", self.project_id) for _ in range(5)]
        self.query = TraceBoundedGraphQuery(
            b"s" * 32, uuid4(), self.project_id, self.refs[0], "DOWNSTREAM",
        )
        self.service = TraceBoundedGraphService(
            unit_of_work=lambda: self.tx, sessions=self.session,
            projects=ProjectAuthorizationService(unit_of_work=lambda: self.tx,
                                                 repository=self.project),
            license_guard=Guard(),
            proofs=TraceTargetProofService({("document", "DOC-02"): self.owner}),
            repository=self.repo, clock=lambda: datetime.now(timezone.utc),
        )

    def edge(self, source, target):
        return TraceAdjacency(uuid4(), TraceEdgeShape(source, target, "DERIVED_FROM"))

    def test_breadth_first_three_depths_in_one_transaction(self):
        a, b, c, d = self.refs[:4]
        ab, ac, bd = self.edge(a, b), self.edge(a, c), self.edge(b, d)
        self.repo.by_root = {a: (ab, ac), b: (bd,)}
        result = self.service.query(self.query)
        self.assertEqual(result.nodes, (a, b, c, d))
        self.assertEqual(result.links, (ab, ac, bd))
        self.assertFalse(result.truncated)
        self.assertEqual(tuple(call[1]["root"] for call in self.repo.calls), (a, b, c, d))
        self.assertTrue(all(tx is self.tx for tx in self.owner.transactions))
        self.assertTrue(all(tx is self.tx for tx, _ in self.repo.calls))

    def test_cycle_does_not_revisit_node(self):
        a, b = self.refs[:2]
        ab, ba = self.edge(a, b), self.edge(b, a)
        self.repo.by_root = {a: (ab,), b: (ba,)}
        result = self.service.query(self.query)
        self.assertEqual(result.nodes, (a, b))
        self.assertEqual(result.links, (ab, ba))
        self.assertEqual(len(self.repo.calls), 2)

    def test_hidden_neighbor_and_root_denial(self):
        a, b = self.refs[:2]
        self.repo.by_root = {a: (self.edge(a, b),)}
        self.owner.denied.add(b)
        result = self.service.query(self.query)
        self.assertEqual(result.nodes, (a,))
        self.assertEqual(result.links, ())
        self.assertTrue(result.truncated)
        self.owner.denied.add(a)
        self.repo.calls.clear()
        with self.assertRaises(TraceQueryError):
            self.service.query(self.query)
        self.assertEqual(self.repo.calls, [])

    def test_depth_and_node_budget_truncate_explicitly(self):
        a, b, c = self.refs[:3]
        self.repo.by_root = {a: (self.edge(a, b), self.edge(a, c)),
                             b: (self.edge(b, c),)}
        depth = self.service.query(replace(self.query, max_depth=1))
        self.assertEqual(depth.nodes, (a, b, c))
        self.assertEqual(tuple(call[1]["root"] for call in self.repo.calls), (a,))
        self.repo.calls.clear()
        budget = self.service.query(replace(self.query, max_nodes=2))
        self.assertEqual(budget.nodes, (a, b))
        self.assertEqual(len(budget.links), 1)
        self.assertTrue(budget.truncated)

    def test_project_denial_and_owner_failure_are_not_empty_graph(self):
        self.project.role = "REMOVED"
        with self.assertRaises(TraceQueryError):
            self.service.query(self.query)
        self.assertEqual(self.repo.calls, [])
        self.project.role = "PROJECT_MANAGER"
        self.owner.fail = True
        with self.assertRaises(TraceQueryError) as caught:
            self.service.query(self.query)
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")

    def test_invalid_query_and_raw_window_rejected_or_truncated(self):
        for bad in (replace(self.query, max_depth=11),
                    replace(self.query, max_nodes=501),
                    replace(self.query, project_id=uuid4())):
            with self.assertRaises(TraceQueryError):
                self.service.query(bad)
        self.assertEqual(self.repo.calls, [])
        a, b = self.refs[:2]
        self.repo.by_root[a] = tuple(self.edge(a, b) for _ in range(101))
        result = self.service.query(self.query)
        self.assertTrue(result.truncated)
        self.assertEqual(len(result.nodes), 2)
        self.assertEqual(len(result.links), 100)

    def test_edge_budget_never_emits_orphan_node(self):
        a, b = self.refs[:2]
        self.repo.by_root[a] = tuple(self.edge(a, b) for _ in range(9))
        result = self.service.query(replace(self.query, max_nodes=2))
        self.assertEqual(result.nodes, (a, b))
        self.assertEqual(len(result.links), 8)
        self.assertTrue(result.truncated)


if __name__ == "__main__":
    unittest.main()
