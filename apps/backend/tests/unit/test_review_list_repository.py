import unittest
from uuid import uuid4

from plm_assistant.modules.review.infrastructure.list_repository import (
    SqlAlchemyReviewListRepository,
)


class ReviewListRepositoryBoundaryTests(unittest.TestCase):
    def test_requires_active_sqlalchemy_transaction_and_bounded_inputs(self):
        repository = SqlAlchemyReviewListRepository()
        values = dict(
            project_id=uuid4(), actor_id=uuid4(), view="all",
            before=None, limit=51,
        )
        for changes in (
            {},
            {"project_id": None},
            {"actor_id": None},
            {"view": "pending"},
            {"limit": 0},
            {"limit": 202},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                repository.list_candidates(object(), **(values | changes))
