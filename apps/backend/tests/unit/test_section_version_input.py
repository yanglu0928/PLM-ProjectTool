from __future__ import annotations

import uuid
import unittest
from dataclasses import replace

from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef,
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


if __name__ == "__main__":
    unittest.main()
