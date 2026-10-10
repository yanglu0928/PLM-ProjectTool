from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy.dialects import postgresql

from plm_assistant.modules.evidence.application.eligibility_record import LockedEvidenceEligibility
from plm_assistant.modules.evidence.infrastructure.eligibility_repository import (
    SqlAlchemyEvidenceEligibilityRepository,
)


class EvidenceEligibilityRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repository = SqlAlchemyEvidenceEligibilityRepository()
        self.evidence_id, self.document_id, self.version_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.project_id = uuid.uuid4()
        self.locked = LockedEvidenceEligibility(
            self.evidence_id, "PROJECT", self.project_id,
            self.document_id, self.version_id, b"a" * 32, "CANDIDATE", 4,
        )

    def test_exists_is_scoped_minimal_read_without_lock_or_flush(self):
        session = Mock()
        session.execute.return_value.scalar_one_or_none.return_value = self.evidence_id
        with patch("plm_assistant.modules.evidence.infrastructure.eligibility_repository._session",
                   return_value=session):
            self.assertTrue(self.repository.exists(object(), scope="PROJECT",
                                                    project_id=self.project_id,
                                                    evidence_id=self.evidence_id))
            session.execute.return_value.scalar_one_or_none.return_value = None
            self.assertFalse(self.repository.exists(object(), scope="PROJECT",
                                                     project_id=self.project_id,
                                                     evidence_id=self.evidence_id))
        statement = session.execute.call_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertTrue(sql.startswith("SELECT"))
        self.assertNotIn("FOR UPDATE", sql)
        self.assertNotIn("content_fingerprint", sql)
        self.assertIn("evd_evidence_records.project_id =", sql)
        self.assertFalse(statement.get_execution_options()["autoflush"])

    def test_lock_scopes_row_and_uses_for_update(self):
        row = SimpleNamespace(
            evidence_id=self.evidence_id, scope="PROJECT", project_id=self.project_id,
            document_id=self.document_id, document_version_id=self.version_id,
            content_fingerprint=b"a" * 32, eligibility_state="CANDIDATE",
            lock_version=4, eligibility_reason=None,
        )
        session = Mock()
        session.execute.return_value.scalar_one_or_none.return_value = row
        with patch("plm_assistant.modules.evidence.infrastructure.eligibility_repository._session",
                   return_value=session):
            actual = self.repository.lock(object(), scope="PROJECT",
                                          project_id=self.project_id,
                                          evidence_id=self.evidence_id)
        self.assertEqual(actual, self.locked)
        statement = session.execute.call_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE OF", sql)
        self.assertIn("evd_evidence_records.scope =", sql)
        self.assertIn("evd_evidence_records.project_id =", sql)

    def test_decide_requires_candidate_and_exact_lock_version(self):
        session = Mock()
        session.execute.return_value.scalar_one_or_none.return_value = 5
        with patch("plm_assistant.modules.evidence.infrastructure.eligibility_repository._session",
                   return_value=session):
            version = self.repository.decide(
                object(), locked=self.locked, state="ELIGIBLE",
                reason="人工已核对原文", actor_id=uuid.uuid4(),
            )
        self.assertEqual(version, 5)
        statement = session.execute.call_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("eligibility_state =", sql)
        self.assertIn("lock_version =", sql)
        self.assertIn("RETURNING", sql)
        self.assertEqual(statement.compile(dialect=postgresql.dialect()).params["eligibility_state_1"],
                         "CANDIDATE")

    def test_no_match_or_bad_transition_cannot_report_success(self):
        session = Mock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        with patch("plm_assistant.modules.evidence.infrastructure.eligibility_repository._session",
                   return_value=session):
            self.assertIsNone(self.repository.decide(
                object(), locked=self.locked, state="INELIGIBLE",
                reason="未找到原始记录", actor_id=uuid.uuid4()))
            with self.assertRaises(ValueError):
                self.repository.decide(object(), locked=self.locked,
                                       state="REVOKED", reason="x", actor_id=uuid.uuid4())


if __name__ == "__main__":
    unittest.main()
