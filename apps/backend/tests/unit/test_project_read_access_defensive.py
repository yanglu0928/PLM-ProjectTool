import unittest
from datetime import datetime, timezone, tzinfo
from types import SimpleNamespace
from sqlalchemy.orm import Session
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess


class NoOffset(tzinfo):
    def utcoffset(self, value):
        return None


class SourceMustNotBeRead:
    @property
    def session(self):
        raise AssertionError('Invalid Project authentication input reached Session source')


class ProjectReadAccessDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.access = SqlAlchemyProjectReadAccess()
        self.args = dict(session_token=b's' * 32, now=datetime.now(timezone.utc))

    def test_invalid_token_refuses_before_session_source(self):
        for value in (None, True, 'Synthetic token', bytearray(b'x' * 32), b'', b'x' * 31, b'x' * 33):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(self.access.authenticated_user(SourceMustNotBeRead(),
                    **(self.args | {'session_token': value})))

    def test_invalid_time_refuses_before_session_source(self):
        for value in (None, True, 'Synthetic time', datetime.now(), datetime.now().replace(tzinfo=NoOffset())):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(self.access.authenticated_user(SourceMustNotBeRead(),
                    **(self.args | {'now': value})))

    def test_genuine_inactive_session_and_wrong_session_do_not_begin(self):
        with Session() as inactive:
            for value in (None, object(), inactive):
                with self.subTest(source_type=type(value).__name__):
                    with self.assertRaisesRegex(RuntimeError, '^active Auth transaction is required$'):
                        self.access.authenticated_user(SimpleNamespace(session=value), **self.args)
                    self.assertFalse(inactive.in_transaction())

    def test_missing_session_source_preserves_original_attribute_error(self):
        for value in (None, SimpleNamespace(), object()):
            with self.subTest(source_type=type(value).__name__), self.assertRaises(AttributeError):
                self.access.authenticated_user(value, **self.args)
