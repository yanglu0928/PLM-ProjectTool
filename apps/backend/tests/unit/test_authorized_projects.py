from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from sqlalchemy.orm import Session

from plm_assistant.modules.project.application.public import ProjectAccessSummary
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects


class AuthorizedProjectsTests(unittest.TestCase):
    def test_public_dto_and_invalid_user(self):
        view = ProjectAccessSummary(uuid.uuid4(), "Project A", "PROJECT_MANAGER")
        self.assertEqual(view.role, "PROJECT_MANAGER")
        with self.assertRaises(ValueError):
            SqlAlchemyAuthorizedProjects().for_user(None, uuid.UUID(int=0))
        with self.assertRaises(ValueError):
            SqlAlchemyAuthorizedProjects().for_user(None, "user")

    def test_invalid_transaction_and_ambiguous_membership_fail_closed(self):
        class Tx:
            session = None

        reader = SqlAlchemyAuthorizedProjects()
        with self.assertRaises(RuntimeError):
            reader.for_user(Tx(), uuid.uuid4())
        session = Session()
        try:
            with session.begin():
                tx = Tx()
                tx.session = session
                class Result:
                    def all(self):
                        return [object(), object()]
                with patch.object(session, "execute", return_value=Result()):
                    with self.assertRaises(RuntimeError):
                        reader.for_user(tx, uuid.uuid4())
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
