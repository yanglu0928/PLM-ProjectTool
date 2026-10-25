from __future__ import annotations

import uuid
import unittest
from dataclasses import replace

from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef,
    OutlineRequirementRef,
    OutlineVersionDraftInput,
    OutlineVersionInputError,
    validate_outline_version_draft,
)


class OutlineVersionInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section_a, self.section_b = uuid.uuid4(), uuid.uuid4()
        self.requirement = OutlineRequirementRef(uuid.uuid4(), uuid.uuid4())
        self.reference = OutlineReferenceRef("GLOBAL", uuid.uuid4(), uuid.uuid4())
        self.value = OutlineVersionDraftInput(
            uuid.uuid4(), uuid.uuid4(), (self.section_a, self.section_b),
            (self.requirement,), (self.reference,),
            ({"kind": "MISSING_SOURCE", "detail": "Confirm interface"},),
            ({"kind": "CONFLICT", "detail": "Two versions differ"},))

    def denied(self, value) -> None:
        with self.assertRaisesRegex(OutlineVersionInputError, "VALIDATION_FAILED"):
            validate_outline_version_draft(value)

    def test_preserves_order_and_canonical_declaration_copy(self) -> None:
        result = validate_outline_version_draft(self.value)
        self.assertEqual(result.section_ids, (self.section_a, self.section_b))
        self.assertEqual(result.requirement_refs, (self.requirement,))
        self.assertEqual(result.reference_refs, (self.reference,))
        self.assertEqual(len(result.request_fingerprint), 32)
        self.assertNotIn("Confirm interface", repr(result))
        copied = result.missing_declarations()
        copied[0]["detail"] = "changed"
        self.assertEqual(result.missing_declarations()[0]["detail"],
                         "Confirm interface")
        reordered = validate_outline_version_draft(replace(
            self.value, section_ids=(self.section_b, self.section_a)))
        self.assertNotEqual(result.request_fingerprint,
                            reordered.request_fingerprint)
        equivalent = validate_outline_version_draft(replace(
            self.value, missing_declarations=(
                {"detail": "Confirm interface", "kind": "MISSING_SOURCE"},)))
        self.assertEqual(result.request_fingerprint,
                         equivalent.request_fingerprint)

    def test_allows_no_reference_when_requirements_exist_or_missing_declared(self) -> None:
        self.assertIsNotNone(validate_outline_version_draft(replace(
            self.value, reference_refs=())))
        self.assertIsNotNone(validate_outline_version_draft(replace(
            self.value, requirement_refs=(), reference_refs=())))
        self.denied(replace(self.value, requirement_refs=(),
                            reference_refs=(), missing_declarations=()))

    def test_rejects_empty_duplicate_and_invalid_id_sets(self) -> None:
        for altered in (
            replace(self.value, section_ids=()),
            replace(self.value, section_ids=(self.section_a, self.section_a)),
            replace(self.value, section_ids=(uuid.UUID(int=0),)),
            replace(self.value, requirement_refs=(self.requirement, self.requirement)),
            replace(self.value, reference_refs=(self.reference, self.reference)),
            replace(self.value, reference_refs=(replace(self.reference, scope="OTHER"),)),
            replace(self.value, project_id=uuid.UUID(int=0)),
        ):
            with self.subTest(altered=altered):
                self.denied(altered)

    def test_rejects_unbounded_or_malformed_declarations(self) -> None:
        nested = []
        for _ in range(1100):
            nested = [nested]
        for altered in (
            replace(self.value, missing_declarations=("free text",)),
            replace(self.value, missing_declarations=({1: "numeric key"},)),
            replace(self.value, missing_declarations=({"score": float("nan")},)),
            replace(self.value, missing_declarations=({"detail": "X" * 65_000},)),
            replace(self.value, missing_declarations=({"nested": nested},)),
            replace(self.value, conflict_declarations=tuple({} for _ in range(101))),
        ):
            with self.subTest(case=type(altered.missing_declarations[0]).__name__):
                self.denied(altered)

    def test_rejects_oversized_collections(self) -> None:
        self.denied(replace(self.value, section_ids=tuple(uuid.uuid4() for _ in range(101))))
        self.denied(replace(self.value, requirement_refs=tuple(
            OutlineRequirementRef(uuid.uuid4(), uuid.uuid4()) for _ in range(501))))
        self.denied(replace(self.value, reference_refs=tuple(
            OutlineReferenceRef("PROJECT", uuid.uuid4(), uuid.uuid4())
            for _ in range(501))))


if __name__ == "__main__":
    unittest.main()
