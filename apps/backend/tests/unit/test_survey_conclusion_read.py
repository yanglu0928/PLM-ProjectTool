from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.survey.application.conclusion_views import (
    SurveyConclusionSummaryView,
)
from plm_assistant.modules.survey.application.read_conclusions import (
    SurveyConclusionReadError, SurveyConclusionReadQuery,
    SurveyConclusionReadService,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Access:
    def authenticated_user(self, transaction, **kwargs):
        return uuid.uuid4()


class Guard:
    def require_valid(self, **kwargs):
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        self.operation = kwargs["operation"]


class Repository:
    rows = ()

    def list_conclusions(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.rows

    def get_conclusion(self, transaction, **kwargs):
        return None


def summary(project):
    return SurveyConclusionSummaryView(
        uuid.uuid4(), uuid.uuid4(), project, uuid.uuid4(), (uuid.uuid4(),),
        (), 1, "DRAFT", (b"f" * 32).hex(), 1, 0, 1, 0,
        None, None, None, uuid.uuid4(), NOW,
    )


class SurveyConclusionReadTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.repository, self.authorization = Repository(), Authorization()
        self.service = SurveyConclusionReadService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=self.authorization, repository=self.repository,
            clock=lambda: NOW,
        )
        self.query = SurveyConclusionReadQuery(
            b"s" * 32, uuid.uuid4(), self.project,
        )

    def test_list_uses_complete_position_and_probe(self):
        rows = (summary(self.project), summary(self.project), summary(self.project))
        self.repository.rows = rows
        page = self.service.list_conclusions(self.query, page_size=2)
        self.assertEqual(rows[:2], page.items)
        self.assertTrue(page.has_more)
        self.assertEqual(
            (NOW, rows[1].survey_conclusion_id),
            (page.next_created_at, page.next_conclusion_id),
        )
        self.assertEqual(3, self.repository.kwargs["limit"])
        self.assertEqual("SURVEY_CONCLUSION_LIST", self.authorization.operation)

    def test_invalid_position_missing_detail_and_repository_shape_fail_closed(self):
        with self.assertRaisesRegex(SurveyConclusionReadError, "VALIDATION_FAILED"):
            self.service.list_conclusions(
                replace(self.query, session_token=b"short"), page_size=10,
            )
        for created, identity in ((NOW, None), (None, uuid.uuid4())):
            with self.subTest(created=created), self.assertRaises(
                    SurveyConclusionReadError):
                self.service.list_conclusions(
                    self.query, page_size=10, after_created_at=created,
                    after_conclusion_id=identity,
                )
        with self.assertRaisesRegex(SurveyConclusionReadError, "RESOURCE_NOT_FOUND"):
            self.service.get_conclusion(self.query, uuid.uuid4())
        self.assertEqual("SURVEY_CONCLUSION_GET", self.authorization.operation)
        self.repository.rows = [summary(self.project)]
        with self.assertRaisesRegex(
            SurveyConclusionReadError, "SURVEY_CONCLUSION_UNAVAILABLE",
        ):
            self.service.list_conclusions(self.query, page_size=1)
        self.assertNotIn("s" * 32, repr(self.query))


if __name__ == "__main__":
    unittest.main()
