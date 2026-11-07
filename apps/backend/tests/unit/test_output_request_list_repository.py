from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.output.infrastructure.list_requests_repository import (
    SqlAlchemyOutputRequestListRepository,
)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class StubSession(Session):
    def __init__(self, rows):
        self.rows, self.statement = rows, None

    def in_transaction(self):
        return True

    def execute(self, statement):
        self.statement = statement
        return Result(self.rows)


class OutputRequestListRepositoryTests(unittest.TestCase):
    def test_query_has_project_scope_keyset_order_and_no_context_body(self):
        project_id, after_id = uuid.uuid4(), uuid.uuid4()
        after_at = datetime(2026, 11, 4, tzinfo=timezone.utc)
        session = StubSession([])
        result = SqlAlchemyOutputRequestListRepository().list_page(
            SimpleNamespace(session=session), project_id=project_id,
            after_requested_at=after_at, after_request_id=after_id, limit=51,
        )
        self.assertEqual(result, ())
        sql = str(session.statement.compile(dialect=postgresql.dialect()))
        self.assertIn("out_output_requests.project_id =", sql)
        self.assertIn("out_output_requests.requested_at <", sql)
        self.assertIn("out_output_requests.output_request_id <", sql)
        self.assertIn("ORDER BY plm.out_output_requests.requested_at DESC", sql)
        self.assertNotIn("context_payload", sql)
        self.assertNotIn("idempotency_key", sql)
        params = set(session.statement.compile(dialect=postgresql.dialect()).params.values())
        self.assertTrue({project_id, after_at, after_id}.issubset(params))


if __name__ == "__main__":
    unittest.main()
