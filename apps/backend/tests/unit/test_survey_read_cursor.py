from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.api.read_cursor import (
    SurveyCursorCodec, SurveyRoundCursorCodec, SurveyVersionCursorCodec,
)


class SurveyReadCursorTests(unittest.TestCase):
    def setUp(self):
        self.project, self.survey = uuid.uuid4(), uuid.uuid4()
        self.session = b"s" * 32
        self.surveys = SurveyCursorCodec(b"a" * 32)
        self.versions = SurveyVersionCursorCodec(b"v" * 32)
        self.rounds = SurveyRoundCursorCodec(b"r" * 32)

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


if __name__ == "__main__":
    unittest.main()
