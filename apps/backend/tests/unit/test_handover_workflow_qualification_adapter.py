import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification,
    HandoverWorkflowEvidenceObservation,
    HandoverWorkflowReviewObservation,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError,
    CurrentChecklistQualificationQuery,
)
from plm_assistant.modules.workflow.application.handover_qualification_adapter import (
    HandoverChecklistQualificationAdapter,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


class Owner:
    def __init__(self, result):
        self.result = result
        self.query = None

    def qualify_only_current_in_transaction(self, transaction, query):
        self.query = query
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class HandoverChecklistQualificationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.analysis = uuid.uuid4()
        self.version = uuid.uuid4()
        self.review = HandoverWorkflowReviewObservation(
            uuid.uuid4(), uuid.uuid4(), self.project, self.analysis,
            self.version, 5, b"v" * 32, NOW,
        )
        self.result = HandoverChecklistQualification(
            "HANDOVER_BASELINE", self.project, self.version, b"q" * 32,
            (HandoverWorkflowEvidenceObservation(
                uuid.uuid4(), self.project, 2, b"e" * 32, NOW,
            ),),
            self.review,
        )
        self.query = CurrentChecklistQualificationQuery(
            b"s" * 32, uuid.uuid4(), self.project,
            "HANDOVER_BASELINE",
        )

    def test_maps_proven_handover_result_without_losing_identity(self):
        owner = Owner(self.result)
        mapped = HandoverChecklistQualificationAdapter(
            owner,
        ).qualify_only_current_in_transaction(object(), self.query)

        self.assertEqual("HANDOVER", mapped.stage_key)
        self.assertEqual(self.analysis, mapped.subject_id)
        self.assertEqual(self.version, mapped.subject_version_id)
        self.assertEqual(self.review.review_round_id,
                         mapped.review.review_round_id)
        self.assertEqual(self.result.content_fingerprint,
                         mapped.content_fingerprint)
        self.assertEqual(self.result.evidence[0].evidence_id,
                         mapped.evidence[0].evidence_id)
        self.assertEqual(self.query.session_token, owner.query.session_token)
        self.assertEqual(self.query.trace_id, owner.query.trace_id)

    def test_rejects_survey_key_and_collapses_owner_failure(self):
        adapter = HandoverChecklistQualificationAdapter(Owner(self.result))
        with self.assertRaises(ChecklistQualificationError):
            adapter.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, uuid.uuid4(), self.project,
                    "SURVEY_CONCLUSION",
                ),
            )
        failed = HandoverChecklistQualificationAdapter(
            Owner(RuntimeError("private")),
        )
        with self.assertRaises(ChecklistQualificationError):
            failed.qualify_only_current_in_transaction(object(), self.query)


if __name__ == "__main__":
    unittest.main()
