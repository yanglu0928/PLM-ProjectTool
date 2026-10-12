from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentProof,
)
from plm_assistant.modules.solution.application.prove_section_evidence_use import (
    SectionEvidenceUseProof,
)
from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    StructuredSpecSourceError,
    StructuredSpecSourceProofService,
)
from plm_assistant.modules.solution.application.read_section import SectionCurrentView
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView,
)
from plm_assistant.modules.solution.application.section_version_input import SectionRequirementRef
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
)


def _payload() -> dict[str, object]:
    return {
        "assumptions": [], "exclusions": [], "source_system": "旧PLM",
        "target_system": "新PLM", "scope": "零件数据",
        "cleansing_rules": ["去重"],
        "field_mappings": [{"source": "old_id", "target": "part_id"}],
        "trial_plan": "试点导入", "reconciliation_plan": "按数量对账",
        "rollback_plan": "恢复快照", "acceptance_criteria": "差异清零",
    }


class StructuredSpecSourceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.req = SpecRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.section = SpecSectionRef(uuid.uuid4(), uuid.uuid4())
        self.evidence_id = uuid.uuid4()
        self.document_version = uuid.uuid4()
        self.token = b"t" * 32
        self.trace = uuid.uuid4()
        self.tx = object()
        self.draft = StructuredSpecDraftInput(
            self.project, None, None, "MIGRATION_SPEC", _payload(),
            (self.req,), (self.section,), (self.evidence_id,), ())
        self.requirement_proof = OutlineApprovedRequirementProof(
            self.project, self.req.requirement_id, self.req.requirement_version_id,
            2, b"r" * 32, uuid.uuid4(), uuid.uuid4())
        self.section_root = SectionCurrentView(
            self.section.solution_section_id, uuid.uuid4(), self.project,
            "migration", "ACTIVE", None, uuid.uuid4(),
            datetime.now(timezone.utc), '"v0"')
        self.section_version = SectionVersionHistoryView(
            self.section.solution_section_version_id, self.section.solution_section_id,
            self.project, 1, "DRAFT", "数据迁移", self.document_version, None,
            b"s" * 32,
            (SectionRequirementRef(self.req.requirement_id, self.req.requirement_version_id),),
            (self.evidence_id,), (), (), None, None, None, uuid.uuid4(),
            datetime.now(timezone.utc))
        self.evidence_proof = SectionEvidenceUseProof(
            self.evidence_id, self.project, uuid.uuid4(), uuid.uuid4(), 2, b"e" * 32)
        self.document_proof = SectionDocumentContentProof(
            self.project, uuid.uuid4(), self.document_version, b"d" * 32)
        self.requirements = Mock()
        self.requirements.prove.return_value = self.requirement_proof
        self.sections = Mock()
        self.sections.get_current.return_value = self.section_root
        self.versions = Mock()
        self.versions.get.return_value = self.section_version
        self.versions.list.return_value = (self.section_version,)
        self.evidence = Mock()
        self.evidence.prove.return_value = self.evidence_proof
        self.documents = Mock()
        self.documents.prove.return_value = self.document_proof
        self.service = StructuredSpecSourceProofService(
            requirements=self.requirements, sections=self.sections,
            versions=self.versions, evidence=self.evidence,
            documents=self.documents)

    def prove(self, draft: StructuredSpecDraftInput | None = None):
        return self.service.prove(
            self.tx, session_token=self.token, trace_id=self.trace,
            draft=draft or self.draft)

    def denied(self, expected: str = "SOURCE_UNAVAILABLE",
               draft: StructuredSpecDraftInput | None = None) -> None:
        with self.assertRaisesRegex(StructuredSpecSourceError, expected):
            self.prove(draft)

    def test_draft_sources_are_composed_in_order_and_bound_to_fingerprint(self) -> None:
        proof = self.prove()
        self.assertEqual(len(proof.content_fingerprint), 32)
        self.assertEqual(proof.requirements, (self.requirement_proof,))
        self.assertEqual(proof.sections, (self.section_version,))
        self.assertEqual(proof.evidence, (self.evidence_proof,))
        self.assertNotIn("旧PLM", repr(proof))
        self.requirements.prove.assert_called_once_with(
            self.tx, project_id=self.project, requirement_id=self.req.requirement_id,
            requirement_version_id=self.req.requirement_version_id)
        self.documents.prove.assert_called_once_with(
            self.tx, session_token=self.token, trace_id=self.trace,
            project_id=self.project, document_version_id=self.document_version)
        self.evidence.prove.assert_called_once_with(
            self.tx, session_token=self.token, trace_id=self.trace,
            project_id=self.project, evidence_id=self.evidence_id)
        self.assertNotEqual(proof.content_fingerprint,
                            self.prove(replace(self.draft, evidence_ids=())).content_fingerprint)
        self.documents.prove.return_value = replace(
            self.document_proof, content_sha256=b"f" * 32)
        self.assertNotEqual(proof.content_fingerprint, self.prove().content_fingerprint)

    def test_approved_section_requires_current_pointer_and_review(self) -> None:
        review, round_id = uuid.uuid4(), uuid.uuid4()
        self.section_version = replace(self.section_version, version_state="APPROVED",
                                       review_ref=review, review_round_ref=round_id)
        self.versions.get.return_value = self.section_version
        self.versions.list.return_value = (self.section_version,)
        self.denied()
        self.section_root = replace(
            self.section_root,
            current_approved_version_ref=self.section.solution_section_version_id)
        self.sections.get_current.return_value = self.section_root
        self.prove()
        self.versions.list.assert_not_called()
        self.versions.get.return_value = replace(self.section_version, review_ref=None)
        self.denied()

    def test_nonapproved_section_must_be_latest_and_active(self) -> None:
        self.versions.list.return_value = (replace(
            self.section_version, solution_section_version_id=uuid.uuid4()),)
        self.denied()
        self.versions.list.return_value = (self.section_version,)
        self.sections.get_current.return_value = replace(self.section_root,
                                                         section_state="ARCHIVED")
        self.denied()
        self.sections.get_current.return_value = self.section_root
        self.versions.get.return_value = replace(self.section_version,
                                                 version_state="RETURNED")
        self.denied()
        self.versions.get.return_value = replace(self.section_version,
                                                 version_state="IN_REVIEW")
        self.denied()
        self.versions.get.return_value = replace(
            self.section_version, version_state="IN_REVIEW",
            review_ref=uuid.uuid4(), review_round_ref=uuid.uuid4())
        self.prove()

    def test_artifact_identity_fails_before_any_source_calls(self) -> None:
        self.denied(draft=replace(self.draft, artifact_ids=(uuid.uuid4(),)))
        self.requirements.prove.assert_not_called()
        self.sections.get_current.assert_not_called()
        self.documents.prove.assert_not_called()

    def test_cross_project_or_mismatched_proofs_fail_closed(self) -> None:
        for port, method, bad in (
            (self.requirements, "prove", replace(self.requirement_proof,
                                                  project_id=uuid.uuid4())),
            (self.requirements, "prove", replace(self.requirement_proof,
                                                  content_fingerprint=b"short")),
            (self.sections, "get_current", replace(self.section_root,
                                                    project_id=uuid.uuid4())),
            (self.versions, "get", replace(self.section_version,
                                           solution_section_version_id=uuid.uuid4())),
            (self.evidence, "prove", replace(self.evidence_proof,
                                             project_id=uuid.uuid4())),
            (self.documents, "prove", replace(self.document_proof,
                                              content_sha256=b"short")),
        ):
            mock = getattr(port, method)
            original = mock.return_value
            mock.return_value = bad
            try:
                with self.subTest(port=method, bad=repr(bad)[:80]):
                    self.denied()
            finally:
                mock.return_value = original

    def test_invalid_context_input_and_port_failure_are_not_authorized(self) -> None:
        with self.assertRaisesRegex(StructuredSpecSourceError, "VALIDATION_FAILED"):
            self.service.prove(None, session_token=self.token, trace_id=self.trace,
                               draft=self.draft)
        with self.assertRaisesRegex(StructuredSpecSourceError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, session_token=b"short", trace_id=self.trace,
                               draft=self.draft)
        self.denied("VALIDATION_FAILED", replace(self.draft, requirement_refs=()))
        self.requirements.prove.side_effect = RuntimeError("internal detail")
        self.denied()


if __name__ == "__main__":
    unittest.main()
