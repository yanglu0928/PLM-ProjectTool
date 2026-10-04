from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisItemView, HandoverAnalysisReadError,
    HandoverAnalysisReadQuery, HandoverAnalysisReadService,
    HandoverAnalysisVersionView, HandoverAnalysisView,
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
    analyses = ()
    versions = ()
    items = ()

    def list_analyses(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.analyses

    def get_analysis(self, transaction, **kwargs):
        return None

    def list_versions(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.versions

    def get_version(self, transaction, **kwargs):
        return None

    def list_items(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.items


class HandoverAnalysisReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.query = HandoverAnalysisReadQuery(
            b"s" * 32, uuid.uuid4(), self.project,
        )
        self.repository = Repository()
        self.authorization = Authorization()
        self.service = HandoverAnalysisReadService(
            unit_of_work=Tx, access=Access(self.actor), license_guard=Guard(),
            authorization=self.authorization, repository=self.repository,
            clock=lambda: self.now,
        )

    def analysis(self, offset: int) -> HandoverAnalysisView:
        return HandoverAnalysisView(
            uuid.uuid4(), self.project, f"Purpose {offset}", "sha256:" + "a" * 64,
            "ACTIVE", None, self.actor, self.now, self.now, '"v0"',
        )

    def version(self, number: int) -> HandoverAnalysisVersionView:
        return HandoverAnalysisVersionView(
            uuid.uuid4(), uuid.uuid4(), self.project, number, "DRAFT",
            "sha256:" + "a" * 64, uuid.uuid4(), uuid.uuid4(), "b" * 64,
            1, 1, 0, 0, 0, None, None, None, self.actor, self.now,
        )

    def item(self, ordinal: int) -> HandoverAnalysisItemView:
        return HandoverAnalysisItemView(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), self.project, ordinal,
            "GAP", "Gap", "Statement", "Impact", "LOW", "LOW", None,
            None, {}, False, "CANDIDATE", (), (), (),
        )

    def test_query_redacts_session_and_rejects_invalid_identity(self):
        self.assertNotIn("s" * 32, repr(self.query))
        for values in (
            {"session_token": b"short"}, {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
        ):
            with self.subTest(values=values), self.assertRaises(
                    HandoverAnalysisReadError) as caught:
                self.service._validate_query(replace(self.query, **values))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_analysis_page_uses_complete_position_and_probe_row(self):
        rows = tuple(self.analysis(index) for index in range(3))
        self.repository.analyses = rows
        page = self.service.list_analyses(self.query, page_size=2)
        self.assertEqual(rows[:2], page.items)
        self.assertTrue(page.has_more)
        self.assertEqual(rows[1].updated_at, page.next_updated_at)
        self.assertEqual(rows[1].handover_analysis_id,
                         page.next_handover_analysis_id)
        self.assertEqual("HND_ANALYSIS_LIST",
                         self.authorization.kwargs["operation"])
        self.assertEqual(3, self.repository.kwargs["limit"])

    def test_rejects_partial_or_invalid_positions(self):
        for values in (
            {"page_size": 0}, {"page_size": 201},
            {"page_size": 1, "after_updated_at": self.now},
            {"page_size": 1, "after_handover_analysis_id": uuid.uuid4()},
            {"page_size": 1, "after_updated_at": self.now.replace(tzinfo=None),
             "after_handover_analysis_id": uuid.uuid4()},
        ):
            with self.subTest(values=values), self.assertRaises(
                    HandoverAnalysisReadError) as caught:
                self.service.list_analyses(self.query, **values)
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_version_page_is_descending_position_contract(self):
        analysis_id = uuid.uuid4()
        rows = (self.version(3), self.version(2), self.version(1))
        self.repository.versions = rows
        page = self.service.list_versions(
            self.query, handover_analysis_id=analysis_id, page_size=2,
            after_version_no=4,
        )
        self.assertEqual(rows[:2], page.items)
        self.assertEqual(2, page.next_version_no)
        self.assertEqual("HND_VERSION_LIST",
                         self.authorization.kwargs["operation"])

    def test_item_page_accepts_zero_position_and_is_bounded(self):
        rows = (self.item(1), self.item(2), self.item(3))
        self.repository.items = rows
        page = self.service.list_items(
            self.query, handover_analysis_id=uuid.uuid4(),
            handover_analysis_version_id=uuid.uuid4(), page_size=2,
            after_ordinal=0,
        )
        self.assertEqual(rows[:2], page.items)
        self.assertEqual(2, page.next_ordinal)
        self.assertEqual("HND_VERSION_ITEM_LIST",
                         self.authorization.kwargs["operation"])

    def test_missing_detail_is_hidden(self):
        for operation in ("analysis", "version"):
            with self.subTest(operation=operation), self.assertRaises(
                    HandoverAnalysisReadError) as caught:
                if operation == "analysis":
                    self.service.get_analysis(self.query, uuid.uuid4())
                else:
                    self.service.get_version(
                        self.query, handover_analysis_id=uuid.uuid4(),
                        handover_analysis_version_id=uuid.uuid4(),
                    )
            self.assertEqual("RESOURCE_NOT_FOUND", caught.exception.code)

    def test_repository_shape_is_fail_closed(self):
        self.repository.analyses = [self.analysis(1)]
        with self.assertRaises(HandoverAnalysisReadError) as caught:
            self.service.list_analyses(self.query, page_size=1)
        self.assertEqual("HANDOVER_UNAVAILABLE", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
