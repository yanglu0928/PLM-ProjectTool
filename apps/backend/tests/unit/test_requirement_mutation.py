from __future__ import annotations

import inspect
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.requirement.application.mutate_requirement import (
    ArchiveRequirementIdentity, DecideRequirementIdentity, PatchRequirementIdentity,
    RequirementIdentityView, RequirementMutationError, RequirementMutationService,
)
from plm_assistant.modules.requirement.infrastructure.requirement_mutation_repository import (
    SqlAlchemyRequirementMutationRepository,
)


class RequirementMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project, self.requirement = uuid.uuid4(), uuid.uuid4()
        common = (b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.requirement, 0)
        self.patch = PatchRequirementIdentity(*common, "REQ-002", str(uuid.uuid4()))
        self.decision = DecideRequirementIdentity(
            *common, "Customer deferred", "Schedule impact", (uuid.uuid4(),), str(uuid.uuid4()))
        self.archive = ArchiveRequirementIdentity(*common, str(uuid.uuid4()))
        self.service = RequirementMutationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object())

    def test_patch_rejects_invalid_identity_or_code_before_io(self) -> None:
        for change in ({"session_token": b"x"}, {"csrf_token": b"x"},
                       {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
                       {"requirement_id": uuid.UUID(int=0)}, {"expected_version": -1},
                       {"requirement_code": ""}, {"requirement_code": "需求-2"},
                       {"requirement_code": "x" * 65}):
            with self.subTest(change=change), self.assertRaises(RequirementMutationError) as caught:
                self.service.patch(replace(self.patch, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_decision_requires_reason_impact_and_unique_bounded_evidence(self) -> None:
        for change in ({"reason": ""}, {"impact": "bad\x00impact"}, {"evidence_ids": ()},
                       {"evidence_ids": (uuid.UUID(int=0),)},
                       {"evidence_ids": (self.decision.evidence_ids[0],) * 2},
                       {"evidence_ids": tuple(uuid.uuid4() for _ in range(101))}):
            with self.subTest(change=change), self.assertRaises(RequirementMutationError) as caught:
                self.service.defer(replace(self.decision, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_view_shape_requires_decision_only_for_defer_or_reject(self) -> None:
        evidence = self.decision.evidence_ids
        view = RequirementIdentityView(
            self.requirement, self.project, "REQ-001", "DEFERRED", uuid.uuid4(),
            "Reason", "Impact", evidence, '"v1"')
        self.assertEqual(view.requirement_state, "DEFERRED")
        with self.assertRaises(ValueError):
            replace(view, decision_ref=None)
        with self.assertRaises(ValueError):
            replace(view, requirement_state="ACTIVE")

    def test_secrets_and_keys_are_redacted(self) -> None:
        for command in (self.patch, self.decision, self.archive):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            self.assertNotIn(command.idempotency_key, rendered)

    def test_repository_proves_evidence_and_uses_root_version_fence(self) -> None:
        source = inspect.getsource(SqlAlchemyRequirementMutationRepository.mutate)
        self.assertIn('EvidenceRow.eligibility_state == "ELIGIBLE"', source)
        self.assertIn('EvidenceRow.scope == "PROJECT"', source)
        self.assertIn("with_for_update", source)
        self.assertIn("CONFLICT_VERSION", source)


if __name__ == "__main__":
    unittest.main()
