from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from types import SimpleNamespace

from plm_assistant.modules.capability.application.requirement_source_proof import (
    CapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.requirement.application.create_version import (
    RequirementAcceptanceDraft, RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionCurrentValidator, RequirementVersionValidationService,
    RequirementVersionValidationSnapshot, ValidateRequirementVersion,
)


class RequirementVersionValidateTests(unittest.TestCase):
    def setUp(self):
        self.project, self.requirement, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.project_evidence, self.standard_evidence = uuid.uuid4(), uuid.uuid4()
        self.baseline, self.item = uuid.uuid4(), uuid.uuid4()
        project_proof = EvidenceRequirementSourceProof(
            self.project_evidence, self.project, uuid.uuid4(), uuid.uuid4(), 0,
            b"p" * 32,
        )
        capability_proof = CapabilityRequirementSourceProof(
            self.baseline, uuid.uuid4(), self.item, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 1, b"c" * 32,
        )
        global_proof = LockedEvidenceSource(
            self.standard_evidence, "GLOBAL", None, uuid.uuid4(), uuid.uuid4(),
            None, {}, b"g" * 32, 0,
        )
        self.project_source = SimpleNamespace(
            prove=lambda *_a, **kwargs: project_proof
            if kwargs["project_id"] == self.project
            and kwargs["evidence_id"] == self.project_evidence else None)
        self.capability_source = SimpleNamespace(
            prove=lambda *_a, **kwargs: capability_proof
            if kwargs["baseline_version_id"] == self.baseline
            and kwargs["capability_item_id"] == self.item else None)
        self.fixed_source = SimpleNamespace(
            get_for_trace=lambda *_a, **kwargs: global_proof
            if kwargs["scope"] == "GLOBAL"
            and kwargs["evidence_id"] == self.standard_evidence else None)
        self.validator = RequirementVersionCurrentValidator(
            survey_sources=object(), handover_sources=object(),
            human_decisions=object(), project_evidence=self.project_source,
            capability_sources=self.capability_source,
            fixed_evidence=self.fixed_source,
        )
        assessment = RequirementCapabilityAssessmentDraft(
            self.baseline, self.item, "DIRECT", "Fully covered",
            "Use standard configuration", "HUMAN", "CONFIRMED",
            (RequirementAssessmentEvidenceDraft(
                self.standard_evidence, "STANDARD"),
             RequirementAssessmentEvidenceDraft(
                self.project_evidence, "PROJECT")),
        )
        self.snapshot = RequirementVersionValidationSnapshot(
            self.version, self.requirement, self.project, 1, "DRAFT", None,
            "Observable requirement", "Business rationale", "PLM", "HIGH",
            "MEDIUM", "STANDARD_FUNCTION", b"0" * 32,
            1, 1, 1, 0, 0, 0, 0,
            (RequirementSourceDraft(
                "PROJECT_EVIDENCE", self.project_evidence, None,
                (self.project_evidence,)),),
            (RequirementAcceptanceDraft(
                "Result is observable", "Execute test", "Project dataset",
                "Windows 11", "Signed report"),),
            (assessment,), (), (), (), (), True,
        )
        found: set[str] = set()
        payload = self.validator._content_payload(self.snapshot, found)
        self.assertEqual(found, set())
        self.snapshot = replace(
            self.snapshot,
            content_fingerprint=canonical_payload_fingerprint(payload),
        )

    def test_valid_standard_version(self):
        self.assertEqual(self.validator.current_issues(object(), self.snapshot), ())

    def test_pending_confirmation_is_not_valid(self):
        pending = replace(self.snapshot, classification="PENDING_CONFIRMATION")
        self.assertIn(
            "PENDING_CONFIRMATION",
            self.validator.current_issues(object(), pending),
        )

    def test_classification_and_acceptance_fail_closed(self):
        invalid = replace(
            self.snapshot, classification="NONSTANDARD_FUNCTION",
            acceptance_criteria=(), declared_acceptance_count=0,
        )
        issues = self.validator.current_issues(object(), invalid)
        self.assertIn("ACCEPTANCE_CRITERIA_MISSING", issues)
        self.assertIn("CLASSIFICATION_INCONSISTENT", issues)

    def test_current_source_capability_and_evidence_are_reobserved(self):
        validator = RequirementVersionCurrentValidator(
            survey_sources=object(), handover_sources=object(),
            human_decisions=object(),
            project_evidence=SimpleNamespace(prove=lambda *_a, **_k: None),
            capability_sources=SimpleNamespace(prove=lambda *_a, **_k: None),
            fixed_evidence=SimpleNamespace(get_for_trace=lambda *_a, **_k: None),
        )
        issues = validator.current_issues(object(), self.snapshot)
        self.assertIn("SOURCE_UNAVAILABLE", issues)
        self.assertIn("CAPABILITY_UNAVAILABLE", issues)
        self.assertIn("EVIDENCE_UNAVAILABLE", issues)

    def test_duplicate_criterion_and_declaration_conflict(self):
        criterion = self.snapshot.acceptance_criteria[0]
        invalid = replace(
            self.snapshot, acceptance_criteria=(criterion, criterion),
            declared_acceptance_count=2,
            assumptions=("Customer provides data",),
            exclusions=("CUSTOMER PROVIDES DATA",),
            declared_assumption_count=1, declared_exclusion_count=1,
        )
        issues = self.validator.current_issues(object(), invalid)
        self.assertIn("ACCEPTANCE_CRITERIA_CONFLICT", issues)
        self.assertIn("DECLARATION_CONFLICT", issues)

    def test_fingerprint_count_and_reason_codec(self):
        invalid = replace(
            self.snapshot, content_fingerprint=b"x" * 32,
            declared_source_count=2, ordinals_contiguous=False,
        )
        issues = self.validator.current_issues(object(), invalid)
        self.assertEqual(issues[:2], (
            "CONTENT_FINGERPRINT_MISMATCH", "COUNT_MISMATCH"))
        reason = RequirementVersionValidationService._reason(issues)
        self.assertEqual(
            RequirementVersionValidationService._issues(reason), issues)

    def test_command_secrets_are_redacted(self):
        command = ValidateRequirementVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.requirement, self.version, "private-key",
        )
        rendered = repr(command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("private-key", rendered)


if __name__ == "__main__":
    unittest.main()
