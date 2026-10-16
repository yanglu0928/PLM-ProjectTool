import unittest
from datetime import datetime, timezone, tzinfo
from types import SimpleNamespace
from sqlalchemy.orm import Session
from plm_assistant.modules.auth.infrastructure.review_start_access import SqlAlchemyReviewStartAccess


class NoOffset(tzinfo):
    def utcoffset(self, value):
        return None


class SessionMustNotBeRead:
    @property
    def session(self):
        raise AssertionError('Invalid authentication input reached transaction source')


class ReviewStartAccessDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.access = SqlAlchemyReviewStartAccess()
        self.inputs = dict(session_token=b's' * 32, csrf_token=b'c' * 32,
                           now=datetime.now(timezone.utc))

    def test_invalid_token_and_csrf_refuse_before_session_source(self):
        for field in ('session_token', 'csrf_token'):
            for value in (None, True, 'Synthetic token', bytearray(b'x' * 32), b'', b'x' * 31, b'x' * 33):
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assertIsNone(self.access.authenticated_user(SessionMustNotBeRead(),
                        **(self.inputs | {field: value})))

    def test_invalid_time_refuses_before_session_source(self):
        for value in (None, True, 'Synthetic time', datetime.now(), datetime.now().replace(tzinfo=NoOffset())):
            with self.subTest(time_type=type(value).__name__):
                self.assertIsNone(self.access.authenticated_user(SessionMustNotBeRead(),
                    **(self.inputs | {'now': value})))

    def test_genuine_inactive_session_and_wrong_source_never_start_transaction(self):
        with Session() as inactive:
            for tx in (None, SimpleNamespace(), SimpleNamespace(session=None),
                       SimpleNamespace(session=object()), SimpleNamespace(session=inactive)):
                with self.subTest(source_type=type(tx).__name__):
                    with self.assertRaisesRegex(RuntimeError, '^active Review authentication transaction required$'):
                        self.access.authenticated_user(tx, **self.inputs)
                    self.assertFalse(inactive.in_transaction())
