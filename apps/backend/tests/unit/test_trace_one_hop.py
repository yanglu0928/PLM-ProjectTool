import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.trace.application.query_one_hop import (
    TraceAdjacency, TraceOneHopQuery, TraceOneHopService, TraceQueryError,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceTargetProof, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Session:
    actor = uuid4()
    valid = True

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor if self.valid else None


class _Project:
    state = "ACTIVE"
    role = "PROJECT_MANAGER"

    def actor_facts(self, *_args, **_kwargs):
        return ProjectActorFacts(self.state, self.role)


class _Guard:
    valid = True

    def require_valid(self, **_kwargs):
        if not self.valid:
            raise RuntimeError("license unavailable")


class _Owner:
    denied = set()
    calls = None

    def prove(self, transaction, query, ref):
        self.calls.append((transaction, ref))
        if ref in self.denied:
            from plm_assistant.modules.trace.application.target_proof import TraceTargetProofError
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        return TraceTargetProof(ref)


class _Repo:
    rows = ()
    calls = None

    def adjacent(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.rows[:kwargs["limit"]]


class TraceOneHopTests(unittest.TestCase):
    def setUp(self):
        self.tx = _Tx()
        self.session, self.project, self.guard = _Session(), _Project(), _Guard()
        self.owner, self.repo = _Owner(), _Repo()
        self.owner.denied, self.owner.calls = set(), []
        self.repo.rows, self.repo.calls = (), []
        project_id = uuid4()
        self.root = TraceVersionRef("document", "DOC-02", uuid4(), uuid4(),
                                    "PROJECT", project_id)
        self.other = TraceVersionRef("document", "DOC-02", uuid4(), uuid4(),
                                     "PROJECT", project_id)
        self.query = TraceOneHopQuery(b"s" * 32, uuid4(), project_id,
                                      self.root, "DOWNSTREAM", limit=2)
        self.service = TraceOneHopService(
            unit_of_work=lambda: self.tx, sessions=self.session,
            projects=ProjectAuthorizationService(unit_of_work=lambda: self.tx,
                                                 repository=self.project),
            license_guard=self.guard,
            proofs=TraceTargetProofService({("document", "DOC-02"): self.owner}),
            repository=self.repo, clock=lambda: datetime.now(timezone.utc),
        )

    def link(self, source=None, target=None):
        return TraceAdjacency(uuid4(), TraceEdgeShape(
            source or self.root, target or self.other, "DERIVED_FROM",
        ))

    def test_current_member_and_both_endpoints_in_same_transaction(self):
        self.repo.rows = (self.link(),)
        result = self.service.query(self.query)
        self.assertEqual(result.links, self.repo.rows)
        self.assertFalse(result.truncated)
        self.assertEqual(self.repo.calls[0][0], self.tx)
        self.assertTrue(all(tx is self.tx for tx, _ in self.owner.calls))
        self.assertEqual(self.repo.calls[0][1]["project_id"], self.query.project_id)

    def test_hidden_neighbor_is_omitted_without_placeholder(self):
        self.repo.rows = (self.link(),)
        self.owner.denied.add(self.other)
        result = self.service.query(self.query)
        self.assertEqual(result.links, ())
        self.assertTrue(result.truncated)

    def test_raw_candidate_window_is_bounded(self):
        self.repo.rows = (self.link(), self.link(), self.link())
        result = self.service.query(self.query)
        self.assertEqual(len(result.links), 2)
        self.assertTrue(result.truncated)
        self.assertEqual(self.repo.calls[0][1]["limit"], 3)

    def test_session_project_license_and_root_denial_prevent_query(self):
        for state in ("session", "project", "license", "root"):
            with self.subTest(state=state):
                self.session.valid = state != "session"
                self.project.role = "REMOVED" if state == "project" else "PROJECT_MANAGER"
                self.guard.valid = state != "license"
                self.owner.denied = {self.root} if state == "root" else set()
                with self.assertRaises(TraceQueryError):
                    self.service.query(self.query)
                self.assertEqual(self.repo.calls, [])

    def test_cross_project_or_wrong_direction_row_fails_closed(self):
        foreign_row = self.link()
        object.__setattr__(foreign_row.edge, "project_id", uuid4())
        self.repo.rows = (foreign_row,)
        with self.assertRaises(TraceQueryError):
            self.service.query(self.query)
        self.repo.rows = (self.link(source=self.other, target=self.root),)
        with self.assertRaises(TraceQueryError):
            self.service.query(self.query)

    def test_invalid_query_does_not_reach_repository(self):
        for bad in (replace(self.query, limit=0),
                    replace(self.query, direction="BOTH"),
                    replace(self.query, project_id=uuid4()),
                    replace(self.query, session_token=b"short")):
            with self.assertRaises(TraceQueryError):
                self.service.query(bad)
        self.assertEqual(self.repo.calls, [])


if __name__ == "__main__":
    unittest.main()
