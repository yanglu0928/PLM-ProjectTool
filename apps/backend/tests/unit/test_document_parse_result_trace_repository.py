from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)


class DocumentParseResultTraceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyParseResultReadRepository()
        self.project_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.record_id = uuid.uuid4()

    def _read(self, method, session: Session):
        return method(
            SimpleNamespace(session=session), scope="PROJECT", project_id=self.project_id,
            document_version_id=self.version_id, parse_record_id=self.record_id,
        )

    def test_trace_read_locks_both_scoped_source_rows_and_refreshes(self) -> None:
        with Session() as session, session.begin(), patch.object(session, "execute") as execute:
            execute.return_value.one_or_none.return_value = None
            self.assertIsNone(self._read(self.repository.get_for_trace, session))
            statement = execute.call_args.args[0]
            sql = str(statement.compile(dialect=postgresql.dialect()))
            self.assertIn("FOR SHARE OF doc_parse_records, doc_parse_result_refs", sql)
            self.assertIn("doc_parse_records.project_id", sql)
            self.assertIn("doc_parse_records.document_version_id", sql)
            self.assertIn("doc_parse_records.parse_state", sql)
            self.assertTrue(statement.get_execution_options()["populate_existing"])

    def test_ordinary_read_does_not_lock_and_inactive_transaction_rejected(self) -> None:
        with Session() as session, session.begin(), patch.object(session, "execute") as execute:
            execute.return_value.one_or_none.return_value = None
            self.assertIsNone(self._read(self.repository.get, session))
            statement = execute.call_args.args[0]
            self.assertNotIn("FOR SHARE", str(statement.compile(dialect=postgresql.dialect())))
            self.assertNotIn("populate_existing", statement.get_execution_options())
        with Session() as session:
            with self.assertRaisesRegex(RuntimeError, "active Document transaction"):
                self._read(self.repository.get_for_trace, session)


if __name__ == "__main__":
    unittest.main()
