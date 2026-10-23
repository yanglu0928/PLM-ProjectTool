from __future__ import annotations

import uuid
import unittest
from dataclasses import replace

from plm_assistant.modules.platform.application.idempotency import canonical_payload_fingerprint
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
    SectionStructuredSpecRef,
    SectionVersionDraftInput,
    SectionVersionInputError,
    validate_section_version_draft,
)


class SectionVersionInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requirement = SectionRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.evidence = uuid.uuid4()
        self.value = SectionVersionDraftInput(
            uuid.uuid4(), uuid.uuid4(), "接口实施方案", uuid.uuid4(), None,
            (self.requirement,), (self.evidence,),
            ({"kind": "ASSUMPTION", "detail": "接口字段待核对"},),
            ({"kind": "EXCLUSION", "detail": "不含历史数据修复"},),
        )

    def denied(self, value: object) -> None:
        with self.assertRaisesRegex(SectionVersionInputError, "VALIDATION_FAILED"):
            validate_section_version_draft(value)

    def test_preserves_fixed_order_and_canonical_copy(self) -> None:
        second = SectionRequirementRef(uuid.uuid4(), uuid.uuid4())
        value = replace(self.value, requirement_refs=(self.requirement, second),
                        evidence_ids=(self.evidence, uuid.uuid4()))
        result = validate_section_version_draft(value)
        self.assertEqual(result.requirement_refs, value.requirement_refs)
        self.assertEqual(result.evidence_ids, value.evidence_ids)
        self.assertEqual(len(result.request_fingerprint), 32)
        self.assertNotIn("接口字段待核对", repr(result))
        copied = result.assumptions()
        copied[0]["detail"] = "mutated"
        self.assertEqual(result.assumptions()[0]["detail"], "接口字段待核对")
        self.assertNotEqual(result.request_fingerprint,
                            validate_section_version_draft(replace(
                                value, requirement_refs=(second, self.requirement)
                            )).request_fingerprint)
        equivalent = replace(value, assumptions=(
            {"detail": "接口字段待核对", "kind": "ASSUMPTION"},))
        self.assertEqual(result.request_fingerprint,
                         validate_section_version_draft(equivalent).request_fingerprint)
        self.assertNotEqual(result.request_fingerprint,
                            validate_section_version_draft(replace(
                                value, evidence_ids=tuple(reversed(value.evidence_ids))
                            )).request_fingerprint)

    def test_content_ref_exactly_one_structural_branch(self) -> None:
        artifact = validate_section_version_draft(replace(
            self.value, content_document_version_ref=None,
            content_artifact_ref=uuid.uuid4()))
        self.assertNotEqual(artifact.request_fingerprint,
                            validate_section_version_draft(self.value).request_fingerprint)
        for altered in (
            replace(self.value, content_document_version_ref=None),
            replace(self.value, content_artifact_ref=uuid.uuid4()),
            replace(self.value, content_artifact_ref="not-an-id"),
            replace(self.value, content_document_version_ref=uuid.UUID(int=0)),
        ):
            with self.subTest(altered=altered):
                self.denied(altered)

    def test_rejects_invalid_title_and_ids(self) -> None:
        for altered in (
            replace(self.value, title=""),
            replace(self.value, title=" padded"),
            replace(self.value, title="x" * 501),
            replace(self.value, title="e\u0301"),
            replace(self.value, title="bad\nline"),
            replace(self.value, project_id=uuid.UUID(int=0)),
            replace(self.value, solution_section_id="not-an-id"),
            replace(self.value, requirement_refs=(
                SectionRequirementRef(uuid.UUID(int=0), uuid.uuid4()),)),
            replace(self.value, evidence_ids=(uuid.UUID(int=0),)),
        ):
            with self.subTest(altered=altered):
                self.denied(altered)

    def test_rejects_duplicate_fixed_refs(self) -> None:
        for altered in (
            replace(self.value, requirement_refs=(self.requirement, self.requirement)),
            replace(self.value, requirement_refs=(
                self.requirement,
                SectionRequirementRef(self.requirement.requirement_id, uuid.uuid4()))),
            replace(self.value, requirement_refs=(
                self.requirement,
                SectionRequirementRef(uuid.uuid4(),
                                      self.requirement.requirement_version_id))),
            replace(self.value, evidence_ids=(self.evidence, self.evidence)),
        ):
            with self.subTest(altered=altered):
                self.denied(altered)

    def test_rejects_unbounded_refs_or_declarations(self) -> None:
        nested: object = []
        for _ in range(1100):
            nested = [nested]
        for altered in (
            replace(self.value, requirement_refs=tuple(
                SectionRequirementRef(uuid.uuid4(), uuid.uuid4())
                for _ in range(501))),
            replace(self.value, evidence_ids=tuple(uuid.uuid4() for _ in range(501))),
            replace(self.value, assumptions=({1: "not string key"},)),
            replace(self.value, assumptions=({"score": float("nan")},)),
            replace(self.value, assumptions=({"detail": "x" * 65_000},)),
            replace(self.value, assumptions=({"nested": nested},)),
            replace(self.value, exclusions=tuple({} for _ in range(101))),
            replace(self.value, exclusions=("free text",)),
        ):
            with self.subTest(case=type(altered).__name__):
                self.denied(altered)

    def test_allows_empty_refs_as_unvalidated_draft_only(self) -> None:
        result = validate_section_version_draft(replace(
            self.value, requirement_refs=(), evidence_ids=(),
            assumptions=(), exclusions=()))
        self.assertEqual(result.requirement_refs, ())
        self.assertEqual(result.evidence_ids, ())

    def test_spec_declaration_is_explicit_bounded_and_legacy_digest_stable(self) -> None:
        legacy = validate_section_version_draft(self.value)
        self.assertEqual(legacy.spec_binding_state, "UNDECLARED")
        self.assertEqual(legacy.structured_spec_refs, ())
        self.assertEqual(legacy.request_fingerprint, canonical_payload_fingerprint({
            "project_id": str(self.value.project_id),
            "solution_section_id": str(self.value.solution_section_id),
            "title": self.value.title,
            "content_document_version_ref": str(self.value.content_document_version_ref),
            "content_artifact_ref": None,
            "requirement_refs": [[str(self.requirement.requirement_id),
                                  str(self.requirement.requirement_version_id)]],
            "evidence_ids": [str(self.evidence)],
            "assumptions": list(self.value.assumptions),
            "exclusions": list(self.value.exclusions),
        }))
        declared = validate_section_version_draft(replace(
            self.value, spec_binding_state="NONE_REQUIRED",
            spec_not_required_reason="No specialist design for this section"))
        self.assertNotEqual(declared.request_fingerprint, legacy.request_fingerprint)
        self.assertNotIn("No specialist design", repr(declared))
        ref = SectionStructuredSpecRef(uuid.uuid4(), uuid.uuid4())
        fixed = validate_section_version_draft(replace(
            self.value, spec_binding_state="FIXED_REFS",
            structured_spec_refs=(ref,)))
        self.assertEqual(fixed.structured_spec_refs, (ref,))
        self.assertNotEqual(fixed.request_fingerprint, declared.request_fingerprint)
        fit_ref = replace(ref, fit_rationale="Matches reviewed interface scope")
        fitted = validate_section_version_draft(replace(
            self.value, spec_binding_state="FIXED_REFS",
            structured_spec_refs=(fit_ref,)))
        self.assertNotEqual(fitted.request_fingerprint, fixed.request_fingerprint)
        self.assertEqual(fitted.structured_spec_refs[0].fit_rationale,
                         "Matches reviewed interface scope")
        self.assertNotIn("Matches reviewed interface scope", repr(fitted))
        for altered in (
            replace(self.value, spec_binding_state="NONE_REQUIRED"),
            replace(self.value, spec_binding_state="NONE_REQUIRED",
                    spec_not_required_reason=" padded"),
            replace(self.value, spec_binding_state="NONE_REQUIRED",
                    spec_not_required_reason="e\u0301"),
            replace(self.value, spec_binding_state="FIXED_REFS"),
            replace(self.value, spec_binding_state="FIXED_REFS",
                    structured_spec_refs=(ref, ref)),
            replace(self.value, spec_binding_state="FIXED_REFS",
                    structured_spec_refs=(SectionStructuredSpecRef(
                        ref.spec_series_id, uuid.uuid4()), ref)),
            replace(self.value, spec_binding_state="UNDECLARED",
                    structured_spec_refs=(ref,)),
            replace(self.value, spec_binding_state="UNKNOWN"),
            *(replace(self.value, spec_binding_state="FIXED_REFS",
                      structured_spec_refs=(replace(ref, fit_rationale=bad),))
              for bad in ("", " padded", "trailing ", "e\u0301", "a\x00b",
                          "x" * 1001, 12)),
        ):
            with self.subTest(altered=altered.spec_binding_state):
                self.denied(altered)


if __name__ == "__main__":
    unittest.main()
