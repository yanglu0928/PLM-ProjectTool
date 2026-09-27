import unittest
from types import SimpleNamespace
from uuid import uuid4
from sqlalchemy.orm import Session
from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames


class ProjectMemberNamesDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.source = SqlAlchemyProjectMemberNames()

    def test_wrong_source_and_real_inactive_session_refuse_without_begin(self):
        with Session() as inactive:
            for value in (None, object(), inactive):
                for ids in ((), (uuid4(),)):
                    with self.subTest(source_type=type(value).__name__, empty=not ids):
                        with self.assertRaisesRegex(RuntimeError, '^active Auth transaction is required$'):
                            self.source.display_names(SimpleNamespace(session=value), ids)
                        self.assertFalse(inactive.in_transaction())

    def test_missing_session_preserves_original_attribute_error(self):
        for value in (None, SimpleNamespace(), object()):
            with self.subTest(source_type=type(value).__name__), self.assertRaises(AttributeError):
                self.source.display_names(value, ())

    def test_empty_tuple_in_real_active_unbound_session_needs_no_sql(self):
        with Session() as session:
            with session.begin():
                self.assertTrue(session.in_transaction())
                self.assertEqual(self.source.display_names(SimpleNamespace(session=session), ()), {})
                self.assertTrue(session.in_transaction())
            self.assertFalse(session.in_transaction())
