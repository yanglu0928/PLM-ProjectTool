from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)


class EvidenceFixedSourceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyEvidenceFixedSourceRepository()
        self.project_id, self.evidence_id = uuid.uuid4(), uuid.uuid4()

    def _read(self, session: Session):
        return self.repository.get_for_trace(
            SimpleNamespace(session=session), scope="PROJECT",
            project_id=self.project_id, evidence_id=self.evidence_id,
        )

    def test_trace_read_requires_current_eligible_scoped_shared_lock(self) -> None:
        with Session() as session, session.begin(), patch.object(session, "execute") as execute:
            execute.return_value.scalar_one_or_none.return_value = None
            self.assertIsNone(self._read(session))
            statement = execute.call_args.args[0]
            sql = str(statement.compile(dialect=postgresql.dialect()))
            self.assertIn("FOR SHARE OF evd_evidence_records", sql)
            for field in ("evidence_id", "scope", "project_id", "eligibility_state"):
                self.assertIn(f"evd_evidence_records.{field}", sql)
            self.assertTrue(statement.get_execution_options()["populate_existing"])

    def test_bad_scope_or_inactive_transaction_rejected(self) -> None:
        with Session() as session:
            with self.assertRaisesRegex(RuntimeError, "active Evidence transaction"):
                self._read(session)
        with Session() as session, session.begin():
            for scope, project in (("PROJECT", None), ("GLOBAL", self.project_id),
                                   ("BAD", None)):
                with self.subTest(scope=scope, project=project):
                    with self.assertRaises(ValueError):
                        self.repository.get_for_trace(
                            SimpleNamespace(session=session), scope=scope,
                            project_id=project, evidence_id=self.evidence_id,
                        )


if __name__ == "__main__":
    unittest.main()
