from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.api.read_cursor import (
    SurveyAssignmentCursorCodec, SurveyConclusionCursorCodec,
    SurveyCursorCodec, SurveyRoundCursorCodec, SurveyVersionCursorCodec,
)


class SurveyReadCursorTests(unittest.TestCase):
    def setUp(self):
        self.project, self.survey = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32
        self.surveys = SurveyCursorCodec(b"a" * 32)
        self.versions = SurveyVersionCursorCodec(b"v" * 32)
        self.rounds = SurveyRoundCursorCodec(b"r" * 32)
        self.assignments = SurveyAssignmentCursorCodec(b"q" * 32)
        self.conclusions = SurveyConclusionCursorCodec(b"c" * 32)

    def test_survey_cursor_binds_full_position_and_context(self):
        instant = datetime(2026, 10, 6, 1, 2, 3, 456789, tzinfo=timezone.utc)
        token = self.surveys.encode(
            project_id=self.project, session_token=self.session, page_size=25,
            updated_at=instant, survey_id=self.survey)
        self.assertEqual((instant, self.survey), self.surveys.decode(
            token, project_id=self.project, session_token=self.session, page_size=25))
        for project, session, size in (
            (uuid.uuid4(), self.session, 25),
            (self.project, b"x" * 32, 25),
            (self.project, self.session, 26),
        ):
            with self.assertRaises(ApplicationError):
                self.surveys.decode(token, project_id=project,
                                    session_token=session, page_size=size)

    def test_version_cursor_binds_parent_and_key(self):
        token = self.versions.encode(
            project_id=self.project, survey_id=self.survey,
            session_token=self.session, page_size=10, position=3)
        self.assertEqual(3, self.versions.decode(
            token, project_id=self.project, survey_id=self.survey,
            session_token=self.session, page_size=10))
        for codec, survey in (
            (self.versions, uuid.uuid4()),
            (SurveyVersionCursorCodec(b"x" * 32), self.survey),
        ):
            with self.assertRaises(ApplicationError):
                codec.decode(token, project_id=self.project, survey_id=survey,
                             session_token=self.session, page_size=10)

    def test_round_cursor_binds_complete_position_and_context(self):
        instant = datetime(2026, 10, 6, 4, 5, 6, 123456, tzinfo=timezone.utc)
        round_id = uuid.uuid4()
        token = self.rounds.encode(
            project_id=self.project, session_token=self.session, page_size=20,
            created_at=instant, round_id=round_id,
        )
        self.assertEqual((instant, round_id), self.rounds.decode(
            token, project_id=self.project, session_token=self.session,
            page_size=20,
        ))
        for codec, project, session, size in (
            (self.rounds, uuid.uuid4(), self.session, 20),
            (self.rounds, self.project, b"x" * 32, 20),
            (self.rounds, self.project, self.session, 21),
            (SurveyRoundCursorCodec(b"x" * 32), self.project, self.session, 20),
        ):
            with self.assertRaises(ApplicationError):
                codec.decode(
                    token, project_id=project, session_token=session,
                    page_size=size,
                )

    def test_assignment_cursor_binds_round_and_complete_position(self):
        instant = datetime(2026, 10, 6, 7, 8, 9, 123456, tzinfo=timezone.utc)
        round_id, assignment_id = uuid.uuid4(), uuid.uuid4()
        token = self.assignments.encode(
            project_id=self.project, survey_round_id=round_id,
            session_token=self.session, page_size=30, created_at=instant,
            assignment_id=assignment_id,
        )
        self.assertEqual((instant, assignment_id), self.assignments.decode(
            token, project_id=self.project, survey_round_id=round_id,
            session_token=self.session, page_size=30,
        ))
        for codec, selected_round in (
            (self.assignments, uuid.uuid4()),
            (SurveyAssignmentCursorCodec(b"x" * 32), round_id),
        ):
            with self.assertRaises(ApplicationError):
                codec.decode(
                    token, project_id=self.project,
                    survey_round_id=selected_round,
                    session_token=self.session, page_size=30,
                )

    def test_conclusion_cursor_has_an_independent_family_and_context(self):
        instant = datetime(2026, 10, 7, 1, 2, 3, 123456, tzinfo=timezone.utc)
        conclusion_id = uuid.uuid4()
        token = self.conclusions.encode(
            project_id=self.project, session_token=self.session, page_size=40,
            created_at=instant, conclusion_id=conclusion_id,
        )
        self.assertEqual((instant, conclusion_id), self.conclusions.decode(
            token, project_id=self.project, session_token=self.session,
            page_size=40,
        ))
        for codec, project, session, size in (
            (self.conclusions, uuid.uuid4(), self.session, 40),
            (self.conclusions, self.project, b"x" * 32, 40),
            (self.conclusions, self.project, self.session, 41),
            (SurveyConclusionCursorCodec(b"x" * 32), self.project,
             self.session, 40),
        ):
            with self.assertRaises(ApplicationError):
                codec.decode(
                    token, project_id=project, session_token=session,
                    page_size=size,
                )


if __name__ == "__main__":
    unittest.main()
