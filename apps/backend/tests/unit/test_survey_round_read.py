from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.survey.application.read_rounds import (
    SurveyRoundReadError,
    SurveyRoundReadQuery,
    SurveyRoundReadService,
)
from plm_assistant.modules.survey.application.round_views import SurveyRoundView


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, transaction, **kwargs):
        return self.actor


class Guard:
    def require_valid(self, **kwargs):
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        self.operation = kwargs["operation"]


class Repository:
    rows = ()

    def list_rounds(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.rows

    def get_round(self, transaction, **kwargs):
        return None


class SurveyRoundReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.repository, self.authorization = Repository(), Authorization()
        self.service = SurveyRoundReadService(
            unit_of_work=Tx, access=Access(self.actor), license_guard=Guard(),
            authorization=self.authorization, repository=self.repository,
            clock=lambda: NOW,
        )
        self.query = SurveyRoundReadQuery(b"s" * 32, uuid.uuid4(), self.project)

    def row(self, number):
        return SurveyRoundView(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), self.project,
            number, "PLANNED", None, None, None, None, None, None, None, None,
            created_by=self.actor, created_at=NOW, updated_at=NOW,
        )

    def test_page_uses_complete_stable_position_and_probe(self):
        rows = (self.row(3), self.row(2), self.row(1))
        self.repository.rows = rows
        page = self.service.list_rounds(self.query, page_size=2)
        self.assertEqual(rows[:2], page.items)
        self.assertTrue(page.has_more)
        self.assertEqual((NOW, rows[1].survey_round_id),
                         (page.next_created_at, page.next_round_id))
        self.assertEqual(3, self.repository.kwargs["limit"])
        self.assertEqual("SURVEY_ROUND_LIST", self.authorization.operation)

    def test_invalid_query_position_and_missing_detail_fail_closed(self):
        with self.assertRaisesRegex(SurveyRoundReadError, "VALIDATION_FAILED"):
            self.service.list_rounds(
                replace(self.query, session_token=b"short"), page_size=10,
            )
        for created, identity in ((NOW, None), (None, uuid.uuid4())):
            with self.subTest(created=created, identity=identity), self.assertRaises(
                    SurveyRoundReadError):
                self.service.list_rounds(
                    self.query, page_size=10,
                    after_created_at=created, after_round_id=identity,
                )
        with self.assertRaisesRegex(SurveyRoundReadError, "RESOURCE_NOT_FOUND"):
            self.service.get_round(self.query, uuid.uuid4())
        self.assertEqual("SURVEY_ROUND_GET", self.authorization.operation)

    def test_repository_shape_and_session_repr_are_safe(self):
        self.repository.rows = [self.row(1)]
        with self.assertRaisesRegex(SurveyRoundReadError, "SURVEY_ROUND_UNAVAILABLE"):
            self.service.list_rounds(self.query, page_size=1)
        self.assertNotIn("s" * 32, repr(self.query))


if __name__ == "__main__":
    unittest.main()
