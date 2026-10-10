from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.handover.application.requirement_source_proof import (
    HandoverRequirementSourceProof,
)
from plm_assistant.modules.handover.infrastructure.requirement_source_proof import (
    SqlAlchemyHandoverRequirementSourceProof,
)
from plm_assistant.modules.survey.application.requirement_source_proof import (
    SurveyConclusionRequirementSourceProof,
)
from plm_assistant.modules.survey.infrastructure.requirement_source_proof import (
    SqlAlchemySurveyConclusionRequirementSourceProof,
)


class RequirementUpstreamSourceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ids = [uuid.uuid4() for _ in range(9)]
        self.project, self.conclusion, self.series, self.survey = self.ids[:4]
        self.analysis, self.analysis_version = self.ids[4:6]
        self.review, self.round = self.ids[6:8]

    @staticmethod
    def _sql(statement) -> str:
        return str(statement.compile(dialect=postgresql.dialect()))

    def test_survey_proof_locks_business_review_round_and_snapshot(self) -> None:
        proof = SqlAlchemySurveyConclusionRequirementSourceProof()
        values = (
            self.conclusion, self.series, self.project, self.survey,
            self.review, self.round, 3, b"s" * 32,
        )
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            execute.return_value.one_or_none.return_value = values
            result = proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                survey_conclusion_id=self.conclusion,
            )
            self.assertEqual(
                result,
                SurveyConclusionRequirementSourceProof(*values),
            )
            sql = self._sql(execute.call_args.args[0])
            for token in (
                "srv_conclusions.conclusion_state", "rvw_reviews.subject_type",
                "rvw_reviews.policy_code", "rvw_review_rounds.round_state",
                "rvw_subject_snapshots.content_fingerprint",
                "FOR SHARE OF srv_conclusions, rvw_reviews, rvw_review_rounds, "
                "rvw_subject_snapshots",
            ):
                self.assertIn(token, sql)
            self.assertTrue(
                execute.call_args.args[0].get_execution_options()[
                    "populate_existing"
                ]
            )
            self.assertNotIn("ssss", repr(result))

    def test_handover_proof_requires_current_version_and_terminal_review(self) -> None:
        proof = SqlAlchemyHandoverRequirementSourceProof()
        values = (
            self.analysis, self.analysis_version, self.project,
            self.review, self.round, 2, b"h" * 32,
        )
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            execute.return_value.one_or_none.return_value = values
            result = proof.prove(
                SimpleNamespace(session=session), project_id=self.project,
                handover_analysis_id=self.analysis,
                handover_analysis_version_id=self.analysis_version,
            )
            self.assertEqual(result, HandoverRequirementSourceProof(*values))
            sql = self._sql(execute.call_args.args[0])
            for token in (
                "hnd_analyses.analysis_state",
                "hnd_analyses.current_approved_version_ref",
                "hnd_analysis_versions.version_state",
                "rvw_reviews.subject_type", "rvw_reviews.policy_code",
                "rvw_review_rounds.subject_version_id",
                "rvw_subject_snapshots.content_fingerprint",
                "FOR SHARE OF hnd_analyses, hnd_analysis_versions, rvw_reviews, "
                "rvw_review_rounds, rvw_subject_snapshots",
            ):
                self.assertIn(token, sql)
            self.assertNotIn("hhhh", repr(result))

    def test_missing_and_invalid_id_fail_closed_without_writes(self) -> None:
        survey = SqlAlchemySurveyConclusionRequirementSourceProof()
        handover = SqlAlchemyHandoverRequirementSourceProof()
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            execute.return_value.one_or_none.return_value = None
            self.assertIsNone(survey.prove(
                SimpleNamespace(session=session), project_id=self.project,
                survey_conclusion_id=self.conclusion,
            ))
            sql = self._sql(execute.call_args.args[0]).lstrip().upper()
            self.assertTrue(sql.startswith("SELECT "))
            execute.reset_mock()
            self.assertIsNone(survey.prove(
                SimpleNamespace(session=session), project_id=uuid.UUID(int=0),
                survey_conclusion_id=self.conclusion,
            ))
            self.assertIsNone(handover.prove(
                SimpleNamespace(session=session), project_id=self.project,
                handover_analysis_id=self.analysis,
                handover_analysis_version_id=uuid.UUID(int=0),
            ))
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
