import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification,
    ChecklistQualificationError,
    ChecklistQualificationEvidence,
    ChecklistQualificationRegistration,
    ChecklistQualificationRegistry,
    ChecklistQualificationReview,
    ChecklistQualificationSubject,
    CurrentChecklistQualificationQuery,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class Owner:
    def __init__(self, result):
        self.result = result

    def qualify_only_current_in_transaction(self, transaction, query):
        return self.result


def subject(project: uuid.UUID, value: int) -> ChecklistQualificationSubject:
    identity = uuid.UUID(int=value)
    version = uuid.UUID(int=value + 100)
    fingerprint = bytes([value]) * 32
    evidence = ChecklistQualificationEvidence(
        uuid.UUID(int=value + 200), project, value, bytes([value + 1]) * 32,
        NOW,
    )
    review = ChecklistQualificationReview(
        uuid.UUID(int=value + 300), uuid.UUID(int=value + 400), project,
        identity, version, value, fingerprint, NOW, "REQ-03",
        "REQUIREMENT_ALL_V1",
    )
    return ChecklistQualificationSubject(
        "REQ-03", identity, version, fingerprint, (evidence,), review,
    )


def qualification(
    item_key: str = "REQUIREMENT_FORMAL_VERSIONS",
) -> AggregateChecklistQualification:
    project = uuid.UUID(int=900)
    return AggregateChecklistQualification(
        project, "REQUIREMENT", item_key,
        (subject(project, 1), subject(project, 2)),
        (ChecklistQualificationEvidence(
            uuid.UUID(int=800), project, 4, b"d" * 32, NOW,
        ),),
        b"s" * 32, b"q" * 32,
    )


class AggregateChecklistQualificationTests(unittest.TestCase):
    def test_keeps_real_subjects_and_exposes_deduplicated_stable_refs(self):
        result = qualification()

        self.assertEqual(
            tuple(value.subject_version_id for value in result.subjects),
            result.subject_version_refs,
        )
        self.assertEqual(
            tuple(value.review.review_round_id for value in result.subjects),
            result.review_round_refs,
        )
        self.assertEqual(
            tuple(sorted((
                result.subjects[0].evidence[0].evidence_id,
                result.subjects[1].evidence[0].evidence_id,
                result.scope_evidence[0].evidence_id,
            ), key=lambda value: value.int)),
            result.evidence_refs,
        )
        self.assertEqual("REQUIREMENT", result.coherence_key[0])
        self.assertEqual(result.scope_fingerprint, result.coherence_key[1])

    def test_registry_routes_aggregate_without_changing_single_owner_contract(self):
        result = qualification()
        registry = ChecklistQualificationRegistry((
            ChecklistQualificationRegistration(
                ("REQUIREMENT_FORMAL_VERSIONS",), Owner(result),
            ),
        ))
        query = CurrentChecklistQualificationQuery(
            b"s" * 32, uuid.uuid4(), result.project_id,
            "REQUIREMENT_FORMAL_VERSIONS",
        )

        self.assertIs(
            result,
            registry.qualify_only_current_in_transaction(object(), query),
        )

    def test_rejects_empty_unsorted_duplicate_and_cross_project_aggregate(self):
        original = qualification()
        other_project = uuid.UUID(int=901)
        bad_subject = replace(
            original.subjects[1],
            review=replace(original.subjects[1].review,
                           project_id=other_project),
        )
        changes = (
            lambda: replace(original, subjects=()),
            lambda: replace(original, subjects=tuple(reversed(
                original.subjects,
            ))),
            lambda: replace(original, subjects=(
                original.subjects[0],
                replace(original.subjects[1],
                        subject_id=original.subjects[0].subject_id,
                        review=replace(
                            original.subjects[1].review,
                            subject_id=original.subjects[0].subject_id,
                        )),
            )),
            lambda: replace(original, subjects=(
                original.subjects[0], bad_subject,
            )),
            lambda: replace(original, scope_fingerprint=b"short"),
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(
                ChecklistQualificationError,
            ):
                change()

    def test_subject_rejects_review_fingerprint_or_identity_drift(self):
        original = qualification().subjects[0]
        for review in (
            replace(original.review, subject_id=uuid.uuid4()),
            replace(original.review, subject_fingerprint=b"x" * 32),
        ):
            with self.subTest(review=review), self.assertRaises(
                ChecklistQualificationError,
            ):
                replace(original, review=review)


if __name__ == "__main__":
    unittest.main()
