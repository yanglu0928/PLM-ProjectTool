from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.output.application.read_request import OutputRequestView
from plm_assistant.modules.output.infrastructure.read_request_repository import (
    SqlAlchemyOutputRequestReadRepository,
)


class Result:
    def __init__(self, row):
        self.row = row

    def one_or_none(self):
        return self.row


class StubSession(Session):
    def __init__(self, row):
        self.row = row
        self.statement = None

    def in_transaction(self):
        return True

    def execute(self, statement):
        self.statement = statement
        return Result(self.row)


class OutputRequestReadRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.project_id, self.request_id = uuid.uuid4(), uuid.uuid4()
        self.template_id, self.context_id = uuid.uuid4(), uuid.uuid4()
        self.source_id, self.job_id = uuid.uuid4(), uuid.uuid4()
        self.now = datetime(2026, 11, 4, tzinfo=timezone.utc)

    def _row(self):
        return SimpleNamespace(
            output_request_id=self.request_id, project_id=self.project_id,
            output_type="DOCX", template_version_ref=self.template_id,
            source_version_refs=[str(self.source_id)],
            output_policy_ref="output.policy.v1", plugin_operation="word.generate",
            context_snapshot_id=self.context_id,
            context_fingerprint=bytes.fromhex("de" * 32),
            request_state="QUEUED", job_ref=self.job_id,
            current_execution_ref=None, generation_no=1,
            requested_at=self.now, completed_at=None, lock_version=3,
        )

    def test_explicit_projection_uses_both_scope_ids_and_never_selects_context_body(self):
        session = StubSession(self._row())
        result = SqlAlchemyOutputRequestReadRepository().get(
            SimpleNamespace(session=session), project_id=self.project_id,
            output_request_id=self.request_id,
        )
        self.assertIs(type(result), OutputRequestView)
        self.assertEqual(result.source_version_refs, (self.source_id,))
        self.assertEqual(result.context_fingerprint, bytes.fromhex("de" * 32))
        compiled = session.statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.assertIn("out_output_requests.project_id =", sql)
        self.assertIn("out_output_requests.output_request_id =", sql)
        self.assertIn("out_context_snapshots.project_id =", sql)
        self.assertNotIn("context_payload", sql)
        self.assertNotIn("idempotency_key", sql)
        self.assertEqual(set(compiled.params.values()),
                         {self.project_id, self.request_id})

    def test_missing_exact_project_request_pair_returns_none(self):
        session = StubSession(None)
        result = SqlAlchemyOutputRequestReadRepository().get(
            SimpleNamespace(session=session), project_id=self.project_id,
            output_request_id=self.request_id,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
