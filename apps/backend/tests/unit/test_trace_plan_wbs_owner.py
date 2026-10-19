from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.entrypoints.trace_plan_wbs_owner import PlanWbsTraceOwner
from plm_assistant.modules.plan.application.read_wbs_for_trace import PlanWbsTraceReadError
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof,
    TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class _Wbs:
    def __init__(self):
        self.calls = []
        self.error = None

    def get_for_trace(self, transaction, query, *, wbs_item_id, plan_version_id):
        self.calls.append((transaction, query, wbs_item_id, plan_version_id))
        if self.error:
            raise PlanWbsTraceReadError(self.error)
        return object()


class PlanWbsTraceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.wbs = _Wbs()
        self.owner = PlanWbsTraceOwner(self.wbs)
        self.project, self.item, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.ref = TraceVersionRef("plan", "PLN-02-WBS", self.item,
                                   self.version, "PROJECT", self.project)
        self.public = TraceResourceVersionRef("PLN-02-WBS", self.item, self.version)
        self.query = TraceProofQuery(b"s" * 32, uuid.uuid4())
        self.transaction = object()

    def test_resolve_and_prove_fixed_wbs_version(self):
        self.assertEqual(self.owner.resolve(
            self.transaction, self.query, self.project, self.public), self.ref)
        self.assertEqual(self.owner.prove(
            self.transaction, self.query, self.ref), TraceTargetProof(self.ref))
        self.assertTrue(all(call[0] is self.transaction for call in self.wbs.calls))
        self.assertEqual(self.wbs.calls[0][1].project_id, self.project)
        self.assertEqual(self.wbs.calls[0][2:], (self.item, self.version))

    def test_wrong_type_and_scope_are_not_queried(self):
        with self.assertRaises(TraceTargetProofError):
            self.owner.resolve(self.transaction, self.query, self.project,
                               replace(self.public, resource_type="PLN-02"))
        with self.assertRaises(TraceTargetProofError):
            self.owner.prove(self.transaction, self.query, TraceVersionRef(
                "plan", "PLN-02", self.item, self.version, "GLOBAL", None))
        self.assertEqual(self.wbs.calls, [])

    def test_error_mapping_hides_unauthorized_target(self):
        for code, expected in (("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"),
                               ("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
                               ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
                               ("PLAN_UNAVAILABLE", "TRACE_UNAVAILABLE")):
            self.wbs.error = code
            with self.subTest(code=code), self.assertRaises(TraceTargetProofError) as caught:
                self.owner.prove(self.transaction, self.query, self.ref)
            self.assertEqual(caught.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
