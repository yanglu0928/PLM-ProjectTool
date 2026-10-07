import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError,
    ChecklistQualificationEvidence,
    ChecklistQualificationRegistration,
    ChecklistQualificationRegistry,
    ChecklistQualificationReview,
    CurrentChecklistQualification,
    CurrentChecklistQualificationQuery,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


class Owner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def qualify_only_current_in_transaction(self, transaction, query):
        self.calls.append((transaction, query))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def qualification(item="HANDOVER_BASELINE"):
    project, subject, version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    review = ChecklistQualificationReview(
        uuid.uuid4(), uuid.uuid4(), project, subject, version, 3,
        b"r" * 32, NOW, "HND-02", "HANDOVER_ALL_V1",
    )
    return CurrentChecklistQualification(
        project, "HANDOVER", item, "HND-02", subject, version,
        b"q" * 32,
        (ChecklistQualificationEvidence(
            uuid.uuid4(), project, 2, b"e" * 32, NOW,
        ),),
        review,
    )


class ChecklistQualificationRegistryTests(unittest.TestCase):
    def test_routes_only_registered_item_and_keeps_result_identity(self):
        result = qualification()
        owner = Owner(result)
        registry = ChecklistQualificationRegistry((
            ChecklistQualificationRegistration(
                ("HANDOVER_BASELINE",), owner,
            ),
        ))
        query = CurrentChecklistQualificationQuery(
            b"s" * 32, uuid.uuid4(), result.project_id,
            "HANDOVER_BASELINE",
        )

        self.assertIs(
            registry.qualify_only_current_in_transaction(object(), query),
            result,
        )
        self.assertEqual(("HANDOVER_BASELINE",), registry.item_keys)
        self.assertIs(query, owner.calls[0][1])
        self.assertEqual(
            ("HND-02", result.subject_id, result.subject_version_id,
             result.review.review_round_id),
            result.coherence_key,
        )

    def test_rejects_duplicate_unknown_and_mismatched_registration(self):
        owner = Owner(qualification())
        with self.assertRaises(ChecklistQualificationError):
            ChecklistQualificationRegistry((
                ChecklistQualificationRegistration(
                    ("HANDOVER_BASELINE",), owner,
                ),
                ChecklistQualificationRegistration(
                    ("HANDOVER_BASELINE",), owner,
                ),
            ))
        registry = ChecklistQualificationRegistry((
            ChecklistQualificationRegistration(
                ("HANDOVER_BASELINE",), owner,
            ),
        ))
        with self.assertRaises(ChecklistQualificationError):
            registry.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, uuid.uuid4(), uuid.uuid4(),
                    "SURVEY_CONCLUSION",
                ),
            )
        bad = replace(owner.result, item_key="HANDOVER_ISSUES")
        wrong = ChecklistQualificationRegistry((
            ChecklistQualificationRegistration(
                ("HANDOVER_BASELINE",), Owner(bad),
            ),
        ))
        with self.assertRaises(ChecklistQualificationError):
            wrong.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, uuid.uuid4(), bad.project_id,
                    "HANDOVER_BASELINE",
                ),
            )

    def test_contract_rejects_empty_cross_project_and_nonapproved_proof(self):
        original = qualification()
        for change in (
            lambda: replace(original, evidence=()),
            lambda: replace(original, evidence=(replace(
                original.evidence[0], project_id=uuid.uuid4(),
            ),)),
            lambda: replace(original, review=replace(
                original.review, observed_state="RETURNED",
            )),
        ):
            with self.subTest(change=change), self.assertRaises(
                ChecklistQualificationError,
            ):
                change()

    def test_owner_failure_is_collapsed(self):
        result = qualification()
        registry = ChecklistQualificationRegistry((
            ChecklistQualificationRegistration(
                ("HANDOVER_BASELINE",), Owner(RuntimeError("private")),
            ),
        ))
        with self.assertRaises(ChecklistQualificationError) as raised:
            registry.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, uuid.uuid4(), result.project_id,
                    "HANDOVER_BASELINE",
                ),
            )
        self.assertEqual("WORKFLOW_GATE_NOT_SATISFIED", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
