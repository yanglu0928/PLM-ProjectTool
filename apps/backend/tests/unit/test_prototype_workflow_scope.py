"""Pure scope rules cannot turn unproved candidates into Workflow PASS."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.prototype.domain.workflow_scope import (
    ApprovedPrototypeCandidate,
    CoverageLinkCandidate,
    CurrentRequirementCandidate,
    NotRequiredDecisionCandidate,
    PrototypeWorkflowScopeError,
    partition_current_scope,
    require_complete_coverage,
)


class PrototypeWorkflowScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.first = CurrentRequirementCandidate(
            self.project, uuid.uuid4(), uuid.uuid4(),
            (uuid.uuid4(), uuid.uuid4()),
        )
        self.second = CurrentRequirementCandidate(
            self.project, uuid.uuid4(), uuid.uuid4(),
            (uuid.uuid4(),),
        )
        self.decision = NotRequiredDecisionCandidate(
            self.project, uuid.uuid4(), uuid.uuid4(),
            (self.second.requirement_version_id,), uuid.uuid4(),
            "人工确认该需求无需交互原型", "方案说明仍需保留影响和依据",
        )
        prototype_version = uuid.uuid4()
        self.prototype = ApprovedPrototypeCandidate(
            self.project, uuid.uuid4(), prototype_version, prototype_version,
            (self.first.requirement_version_id,), "ACTIVE", "APPROVED",
        )
        self.link = CoverageLinkCandidate(
            self.project, self.first.requirement_version_id,
            self.prototype.prototype_version_id, "VALIDATES",
            self.first.acceptance_criterion_refs, (), "ACTIVE",
        )

    def partition(self, *, requirements=None, decisions=None, prototypes=None):
        return partition_current_scope(
            project_id=self.project,
            requirements=(self.first, self.second)
                if requirements is None else requirements,
            decisions=(self.decision,) if decisions is None else decisions,
            prototypes=(self.prototype,) if prototypes is None else prototypes,
        )

    def test_mixed_scope_and_complete_link(self):
        result = self.partition()
        self.assertEqual(result.required_requirement_version_refs,
                         (self.first.requirement_version_id,))
        self.assertEqual(result.not_required_requirement_version_refs,
                         (self.second.requirement_version_id,))
        self.assertFalse(result.all_not_required)
        require_complete_coverage(result, (self.link,))

    def test_all_not_required_is_explicitly_decided_not_empty_skipped(self):
        decision = replace(self.decision, affected_requirement_version_refs=(
            self.first.requirement_version_id,
            self.second.requirement_version_id,
        ))
        result = self.partition(decisions=(decision,), prototypes=())
        self.assertTrue(result.all_not_required)
        require_complete_coverage(result, ())
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(requirements=(), decisions=(decision,), prototypes=())

    def test_missing_or_cross_project_requirement_fails(self):
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(decisions=())
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(requirements=(replace(self.first,
                project_id=uuid.uuid4()), self.second))
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(requirements=(self.first, self.first))

    def test_conflicting_or_stale_decision_fails(self):
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(decisions=(replace(self.decision,
                affected_requirement_version_refs=(
                    self.first.requirement_version_id,)),))
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(decisions=(self.decision, replace(self.decision,
                decision_id=uuid.uuid4(), prototype_id=uuid.uuid4())))
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(decisions=(replace(self.decision,
                affected_requirement_version_refs=(uuid.uuid4(),)),))

    def test_draft_or_stale_prototype_pointer_fails(self):
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(prototypes=(replace(self.prototype,
                version_state="IN_REVIEW"),))
        with self.assertRaises(PrototypeWorkflowScopeError):
            self.partition(prototypes=(replace(self.prototype,
                current_approved_version_ref=uuid.uuid4()),))

    def test_illustration_or_partial_coverage_cannot_pass(self):
        partition = self.partition()
        with self.assertRaises(PrototypeWorkflowScopeError):
            require_complete_coverage(partition, ())
        illustration = replace(self.link, purpose="ILLUSTRATES")
        with self.assertRaises(PrototypeWorkflowScopeError):
            require_complete_coverage(partition, (illustration,))
        partial = replace(self.link,
            covered_acceptance_criterion_refs=(
                self.first.acceptance_criterion_refs[0],),
            uncovered_acceptance_criterion_refs=(
                self.first.acceptance_criterion_refs[1],))
        with self.assertRaises(PrototypeWorkflowScopeError):
            require_complete_coverage(partition, (partial,))
        second = replace(partial,
            purpose="ACCEPTANCE_REFERENCE",
            covered_acceptance_criterion_refs=(
                self.first.acceptance_criterion_refs[1],),
            uncovered_acceptance_criterion_refs=(
                self.first.acceptance_criterion_refs[0],))
        require_complete_coverage(partition, (partial, second))

    def test_stale_or_wrong_project_link_fails(self):
        partition = self.partition()
        for bad in (
            replace(self.link, project_id=uuid.uuid4()),
            replace(self.link, prototype_version_id=uuid.uuid4()),
            replace(self.link, requirement_version_id=uuid.uuid4()),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(PrototypeWorkflowScopeError):
                    require_complete_coverage(partition, (bad,))
        with self.assertRaises(PrototypeWorkflowScopeError):
            replace(self.link, link_state="REVOKED")


if __name__ == "__main__":
    unittest.main()
