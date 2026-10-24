from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionReadError, HandoverActionReadQuery,
    HandoverActionReadService, HandoverActionSummaryView,
)


class Repository:
    def __init__(self, rows=()):
        self.rows = rows

    def list_page(self, transaction, **kwargs):
        self.kwargs = kwargs
        return self.rows

    def get(self, transaction, **kwargs):
        return None


class HandoverActionReadValidationTests(unittest.TestCase):
    def setUp(self):
        self.query = HandoverActionReadQuery(
            b"s" * 32, uuid.uuid4(), uuid.uuid4(),
        )

    def test_rejects_invalid_query_and_page_position(self):
        invalid = (
            {"session_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionReadError) as caught:
                HandoverActionReadService._validate_query(
                    replace(self.query, **values),
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_command_repr_redacts_session(self):
        self.assertNotIn("s" * 32, repr(self.query))

    def test_page_uses_complete_stable_position(self):
        service = HandoverActionReadService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(),
        )
        now = datetime.now(timezone.utc)
        for values in (
            {"page_size": 0}, {"page_size": 201},
            {"page_size": 10, "after_updated_at": now},
            {"page_size": 10, "after_action_item_id": uuid.uuid4()},
            {"page_size": 10, "after_updated_at": now.replace(tzinfo=None),
             "after_action_item_id": uuid.uuid4()},
        ):
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionReadError) as caught:
                service.list_page(self.query, **values)
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_page_drops_probe_row_and_returns_tail_position(self):
        now = datetime.now(timezone.utc)
        project = self.query.project_id
        def item(offset):
            return HandoverActionSummaryView(
                uuid.uuid4(), project, "HUMAN", "OTHER", str(offset),
                uuid.uuid4(), now, "LOW", "OPEN", None, None, None, None,
                now, '"v0"',
            )
        repository = Repository((item(1), item(2), item(3)))
        service = HandoverActionReadService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=repository,
        )
        page = service._page(object(), project, 2, None, None)
        self.assertEqual(2, len(page.items))
        self.assertTrue(page.has_more)
        self.assertEqual(page.items[-1].action_item_id,
                         page.next_action_item_id)


if __name__ == "__main__":
    unittest.main()
