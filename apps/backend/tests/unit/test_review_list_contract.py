from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.review.application.list_contract import (
    MyReviewAssignmentSummary, ReviewListActiveRoundSummary,
    ReviewListContractError, ReviewListItem, ReviewListPage,
    ReviewListPosition, ReviewListQuery,
)


class ReviewListContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 19, 5, 30, tzinfo=timezone.utc)
        self.project = uuid.uuid4()
        self.position = ReviewListPosition(self.now, uuid.uuid4())
        self.assignment = MyReviewAssignmentSummary(
            uuid.uuid4(), "PENDING", None, None,
        )
        self.round = ReviewListActiveRoundSummary(
            uuid.uuid4(), 1, uuid.uuid4(), self.now, self.assignment,
        )
        self.item = ReviewListItem(
            self.position.review_id, self.project, "SOL-06", uuid.uuid4(),
            "STRUCTURED_SPEC_ALL_V1", "IN_REVIEW", uuid.uuid4(), self.now,
            '"v1"', self.round,
        )

    def test_query_position_item_and_short_page_contract(self) -> None:
        query = ReviewListQuery(
            b"s" * 32, uuid.uuid4(), self.project,
            view="my_pending", before=self.position, page_size=25,
        )
        self.assertEqual(query.before, self.position)
        self.assertEqual(self.item.position, self.position)
        page = ReviewListPage((), self.position, True)
        self.assertEqual(page.items, ())
        self.assertTrue(page.has_more)

    def test_terminal_item_has_no_active_round(self) -> None:
        terminal = replace(self.item, state="APPROVED", active_round=None)
        terminal.__post_init__()
        decided = MyReviewAssignmentSummary(
            uuid.uuid4(), "DECIDED", "APPROVE", self.now,
        )
        decided.__post_init__()

    def test_invalid_queries_and_projection_shapes_rejected(self) -> None:
        valid_query = ReviewListQuery(b"s" * 32, uuid.uuid4(), self.project)
        invalid_queries = (
            lambda: replace(valid_query, session_token=b"short"),
            lambda: replace(valid_query, view="assigned"),
            lambda: replace(valid_query, page_size=201),
        )
        for create in invalid_queries:
            with self.assertRaises(ReviewListContractError):
                create()
        invalid_projections = (
            lambda: replace(self.assignment, state="DECIDED"),
            lambda: replace(
                self.assignment, state="PENDING", decision="APPROVE"),
            lambda: replace(self.item, state="APPROVED"),
            lambda: replace(self.item, etag="v1"),
            lambda: ReviewListPage((self.item,), None, True),
        )
        for create in invalid_projections:
            with self.assertRaises(ReviewListContractError):
                create()


if __name__ == "__main__":
    unittest.main()
