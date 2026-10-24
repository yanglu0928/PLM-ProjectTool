from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.auth.application.session_service import PasswordIssueProof
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess


class PasswordIssueAccessTests(unittest.TestCase):
    def test_requires_verifier(self):
        with self.assertRaises(ValueError):
            SqlAlchemyPasswordIssueAccess(None)

    def test_unexpected_or_invalid_proof_fails_before_database(self):
        access = SqlAlchemyPasswordIssueAccess(object())
        for proof in (True, object(), PasswordIssueProof(bytearray()), PasswordIssueProof(bytearray(b"x" * 1025))):
            self.assertFalse(access.can_issue(None, uuid.uuid4(), 1, proof))

    def test_valid_shape_requires_active_transaction(self):
        access = SqlAlchemyPasswordIssueAccess(object())
        with self.assertRaisesRegex(RuntimeError, "active auth transaction"):
            access.can_issue(None, uuid.uuid4(), 1, PasswordIssueProof(bytearray(b"synthetic")))


if __name__ == "__main__":
    unittest.main()
