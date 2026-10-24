from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineApprovedRequirementProof,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef,
    OutlineRequirementRef,
    OutlineVersionDraftInput,
)
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseProof
from plm_assistant.modules.solution.application.prove_outline_version_input import (
    CurrentOutlineVersionBase,
    OutlineVersionInputProofError,
    OutlineVersionInputProofService,
)
from plm_assistant.modules.solution.application.prove_reference_use import EligibleReferenceUseProof


class OutlineVersionInputProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tx = object()
        self.trace = uuid.uuid4()
        self.project, self.outline, self.section = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.requirement = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.reference = OutlineReferenceRef("GLOBAL", uuid.uuid4(), uuid.uuid4())
        self.event, self.confirmation = uuid.uuid4(), uuid.uuid4()
        self.draft = OutlineVersionDraftInput(
            self.project, self.outline, (self.section,), (self.requirement,),
            (self.reference,), (), ())
        self.bases, self.sections, self.requirements, self.references = (
            Mock(), Mock(), Mock(), Mock())
        self.bases.current.return_value = CurrentOutlineVersionBase(
            self.project, self.outline, 1, None, 0)
        self.sections.prove.return_value = OutlineSectionUseProof(
            self.project, self.outline, self.section)
        self.requirements.prove.return_value = OutlineApprovedRequirementProof(
            self.project, self.requirement.requirement_id,
            self.requirement.requirement_version_id, 1, b"r" * 32,
            uuid.uuid4(), uuid.uuid4())
        self.references.prove.return_value = EligibleReferenceUseProof(
            self.reference.reference_solution_id,
            self.reference.reference_version_id, "GLOBAL", self.project,
            b"g" * 32, self.event, self.confirmation)
        self.service = OutlineVersionInputProofService(
            bases=self.bases, sections=self.sections,
            requirements=self.requirements, references=self.references)

    def prove(self):
        return self.service.prove(self.tx, trace_id=self.trace, draft=self.draft)

    def denied(self):
        with self.assertRaises(OutlineVersionInputProofError):
            self.prove()

    def test_full_fixed_input_produces_opaque_content_fingerprint(self) -> None:
        result = self.prove()
        self.assertEqual(result.next_version_no, 1)
        self.assertEqual(result.root_lock_version, 0)
        self.assertEqual(len(result.content_fingerprint), 32)
        self.assertNotIn((b"g" * 32).hex(), repr(result))
        self.assertNotEqual(result.content_fingerprint,
                            result.draft.request_fingerprint)
        self.bases.current.assert_called_once_with(
            self.tx, project_id=self.project, outline_id=self.outline)

    def test_content_changes_with_current_source_or_base(self) -> None:
        original = self.prove()
        self.references.prove.return_value = replace(
            self.references.prove.return_value, source_fingerprint=b"x" * 32)
        self.assertNotEqual(self.prove().content_fingerprint,
                            original.content_fingerprint)
        self.bases.current.return_value = CurrentOutlineVersionBase(
            self.project, self.outline, 2, uuid.uuid4(), 1)
        self.assertNotEqual(self.prove().content_fingerprint,
                            original.content_fingerprint)

    def test_scope_identity_and_missing_proofs_fail_closed(self) -> None:
        self.references.prove.return_value = replace(
            self.references.prove.return_value, target_project_id=uuid.uuid4())
        self.denied()
        self.references.prove.return_value = None
        self.denied()
        self.bases.current.return_value = replace(
            self.bases.current.return_value, project_id=uuid.uuid4())
        self.denied()

    def test_invalid_draft_and_exception_fail_closed(self) -> None:
        with self.assertRaisesRegex(OutlineVersionInputProofError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, trace_id=self.trace,
                               draft=replace(self.draft, section_ids=()))
        self.requirements.prove.side_effect = RuntimeError("unavailable")
        self.denied()


if __name__ == "__main__":
    unittest.main()
