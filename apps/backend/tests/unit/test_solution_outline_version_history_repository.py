from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository, _ordered,
)


class OutlineVersionHistoryRepositoryTests(unittest.TestCase):
    def test_ordered_fixed_collection_is_complete_or_fails_closed(self):
        _ordered((SimpleNamespace(ordinal=1), SimpleNamespace(ordinal=2)), 2)
        for rows, count in (
            ((), 1),
            ((SimpleNamespace(ordinal=2),), 1),
            ((SimpleNamespace(ordinal=1), SimpleNamespace(ordinal=3)), 2),
        ):
            with self.subTest(rows=rows, count=count), self.assertRaises(RuntimeError):
                _ordered(rows, count)

    def test_invalid_or_foreign_identity_never_hits_database(self):
        repository = SqlAlchemyOutlineVersionReadRepository()
        identity = uuid.uuid4()
        self.assertIsNone(repository.get(None, project_id=identity,
                                         outline_id=identity, version_id=uuid.UUID(int=0)))
        with self.assertRaises(ValueError):
            repository.list(None, project_id=identity, outline_id=identity,
                            before_version_no=None, limit=0)
        with self.assertRaises(ValueError):
            repository.list(None, project_id=identity, outline_id=identity,
                            before_version_no=1, limit=10)
