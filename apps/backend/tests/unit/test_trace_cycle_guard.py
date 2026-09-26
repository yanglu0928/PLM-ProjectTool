from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from sqlalchemy.orm import Session

from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.cycle_guard import SqlAlchemyTraceCycleGuard


class TraceCycleGuardBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        project = uuid.uuid4()
        self.source = TraceVersionRef("document", "DOC-02", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", project)
        self.target = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", project)
        self.guard = SqlAlchemyTraceCycleGuard()

    def test_controlled_relation_requires_active_transaction(self) -> None:
        edge = TraceEdgeShape(self.source, self.target, "DERIVED_FROM")
        with Session() as session, self.assertRaises(RuntimeError):
            self.guard.assert_acyclic(SimpleNamespace(session=session), edge)

    def test_other_relation_does_not_run_controlled_graph_query(self) -> None:
        edge = TraceEdgeShape(self.source, self.target, "REFINES")
        self.guard.assert_acyclic(object(), edge)

    def test_unvalidated_edge_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.guard.assert_acyclic(object(), object())


if __name__ == "__main__":
    unittest.main()
