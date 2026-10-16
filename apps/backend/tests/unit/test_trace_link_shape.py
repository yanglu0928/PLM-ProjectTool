from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.trace.domain.link_shape import (
    TraceEdgeShape, TraceShapeError, TraceVersionRef,
)


class TraceLinkShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.source = TraceVersionRef("document", "DOC-02", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", self.project)
        self.target = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", self.project)

    def test_same_project_and_global_edges(self) -> None:
        edge = TraceEdgeShape(self.source, self.target, "DERIVED_FROM")
        self.assertEqual((edge.scope, edge.project_id), ("PROJECT", self.project))
        global_doc = replace(self.source, scope="GLOBAL", project_id=None)
        global_capability = TraceVersionRef("capability", "CAP-02", uuid.uuid4(),
                                            uuid.uuid4(), "GLOBAL", None)
        self.assertEqual(TraceEdgeShape(global_doc, global_capability,
                                        "REFINES").scope, "GLOBAL")
        self.assertEqual(TraceEdgeShape(global_doc, self.target,
                                        "DERIVED_FROM").project_id, self.project)
        self.assertEqual(TraceEdgeShape(global_capability, self.target,
                                        "REFERENCES_CAPABILITY").project_id,
                         self.project)

    def test_unknown_types_unversioned_or_bad_scope_rejected(self) -> None:
        for changes in (
            {"owner_module": "auth", "object_type": "AUT-02"},
            {"owner_module": "document", "object_type": "DOC-03"},
            {"owner_module": "requirement", "object_type": "DOC-02"},
            {"object_id": uuid.UUID(int=0)},
            {"version_id": uuid.UUID(int=0)},
            {"version_id": None},
            {"scope": "PROJECT", "project_id": None},
            {"scope": "GLOBAL", "project_id": self.project},
        ):
            with self.subTest(changes=changes), self.assertRaises(TraceShapeError):
                replace(self.source, **changes)

    def test_self_cross_project_project_to_global_and_direction_rejected(self) -> None:
        global_target = replace(self.target, scope="GLOBAL", project_id=None)
        foreign_target = replace(self.target, project_id=uuid.uuid4())
        global_source = replace(self.source, scope="GLOBAL", project_id=None)
        for source, target, relation in (
            (self.source, self.source, "DERIVED_FROM"),
            (self.source, foreign_target, "REFINES"),
            (self.source, global_target, "DERIVED_FROM"),
            (global_source, self.target, "IMPLEMENTS"),
            (global_source, self.target, "REFERENCES_CAPABILITY"),
            (self.source, self.target, "REFERENCES_CAPABILITY"),
            (self.source, self.target, "SUPPORTS"),
        ):
            with self.subTest(relation=relation), self.assertRaises(TraceShapeError):
                TraceEdgeShape(source, target, relation)

    def test_supersede_distinct_versions_not_self_loop(self) -> None:
        later = replace(self.source, version_id=uuid.uuid4())
        self.assertEqual(TraceEdgeShape(later, self.source, "SUPERSEDES").scope,
                         "PROJECT")

    def test_caller_cannot_forge_edge_scope(self) -> None:
        with self.assertRaises(TraceShapeError):
            TraceEdgeShape(self.source, self.target, "REFINES", "GLOBAL", None)
        with self.assertRaises(TraceShapeError):
            TraceEdgeShape(self.source, self.target, "REFINES", "PROJECT", uuid.uuid4())


if __name__ == "__main__":
    unittest.main()
