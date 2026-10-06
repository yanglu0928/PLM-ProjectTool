from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.survey.application.read_surveys import (
    SurveyReadError, SurveyReadQuery, SurveyReadService, SurveyVersionView,
    SurveyView,
)


class Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Guard:
    def require_valid(self, *, trace_id):
        self.trace_id = trace_id


class Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, transaction, *, session_token, now):
        self.now = now
        return self.actor


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        self.kwargs = kwargs


class Repository:
    surveys = ()
    versions = ()

    def list_surveys(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.surveys

    def get_survey(self, transaction, **kwargs):
        return None

    def list_versions(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.versions

    def get_version(self, transaction, **kwargs):
        return None


class SurveyReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.query = SurveyReadQuery(b"s" * 32, uuid.uuid4(), self.project)
        self.repository = Repository()
        self.authorization = Authorization()
        self.service = SurveyReadService(
            unit_of_work=Tx, access=Access(self.actor), license_guard=Guard(),
            authorization=self.authorization, repository=self.repository,
            clock=lambda: self.now,
        )

    def survey(self, offset: int) -> SurveyView:
        return SurveyView(
            uuid.uuid4(), self.project, f"Survey {offset}", "ACTIVE", None,
            self.actor, self.now, None, self.now, '"v0"',
        )

    def version(self, number: int) -> SurveyVersionView:
        return SurveyVersionView(
            uuid.uuid4(), uuid.uuid4(), self.project, number, "DRAFT",
            "a" * 64, 1, 0, 1, 1, None, None, None, self.actor, self.now,
        )

    def test_query_redacts_session_and_rejects_invalid_identity(self):
        self.assertNotIn("s" * 32, repr(self.query))
        for values in (
            {"session_token": b"short"}, {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
        ):
            with self.subTest(values=values), self.assertRaises(
                    SurveyReadError) as caught:
                self.service._validate_query(replace(self.query, **values))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_survey_page_uses_complete_position_and_probe_row(self):
        rows = tuple(self.survey(index) for index in range(3))
        self.repository.surveys = rows
        page = self.service.list_surveys(self.query, page_size=2)
        self.assertEqual(rows[:2], page.items)
        self.assertTrue(page.has_more)
        self.assertEqual(rows[1].updated_at, page.next_updated_at)
        self.assertEqual(rows[1].survey_id, page.next_survey_id)
        self.assertEqual("SURVEY_LIST", self.authorization.kwargs["operation"])
        self.assertEqual(3, self.repository.kwargs["limit"])

    def test_rejects_partial_or_invalid_positions(self):
        for values in (
            {"page_size": 0}, {"page_size": 201},
            {"page_size": 1, "after_updated_at": self.now},
            {"page_size": 1, "after_survey_id": uuid.uuid4()},
            {"page_size": 1, "after_updated_at": self.now.replace(tzinfo=None),
             "after_survey_id": uuid.uuid4()},
        ):
            with self.subTest(values=values), self.assertRaises(
                    SurveyReadError) as caught:
                self.service.list_surveys(self.query, **values)
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_version_page_is_descending_position_contract(self):
        survey_id = uuid.uuid4()
        rows = (self.version(3), self.version(2), self.version(1))
        self.repository.versions = rows
        page = self.service.list_versions(
            self.query, survey_id=survey_id, page_size=2, after_version_no=4,
        )
        self.assertEqual(rows[:2], page.items)
        self.assertEqual(2, page.next_version_no)
        self.assertEqual("SURVEY_VERSION_LIST",
                         self.authorization.kwargs["operation"])

    def test_version_position_must_be_positive_integer(self):
        for position in (0, -1, True, "1"):
            with self.subTest(position=position), self.assertRaises(
                    SurveyReadError) as caught:
                self.service.list_versions(
                    self.query, survey_id=uuid.uuid4(), page_size=1,
                    after_version_no=position,
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_missing_details_are_hidden(self):
        for operation in ("survey", "version"):
            with self.subTest(operation=operation), self.assertRaises(
                    SurveyReadError) as caught:
                if operation == "survey":
                    self.service.get_survey(self.query, uuid.uuid4())
                else:
                    self.service.get_version(
                        self.query, survey_id=uuid.uuid4(),
                        survey_version_id=uuid.uuid4(),
                    )
            self.assertEqual("RESOURCE_NOT_FOUND", caught.exception.code)

    def test_repository_shape_is_fail_closed(self):
        self.repository.surveys = [self.survey(1)]
        with self.assertRaises(SurveyReadError) as caught:
            self.service.list_surveys(self.query, page_size=1)
        self.assertEqual("SURVEY_UNAVAILABLE", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
