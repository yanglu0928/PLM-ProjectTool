from types import SimpleNamespace
import unittest
from uuid import uuid4
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError, IdempotencyResult, IdempotencyScope
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.scope = IdempotencyScope(uuid4(), None, 'V1_AUTH_LOGOUT', b'k'*32)
        self.result = IdempotencyResult('V1_AUTH_SESSION', uuid4(), 200)
        self.statements = []
        self.row = ('COMPLETED', b'f'*32, self.result.ref_type, self.result.ref_id, 200)
        def execute(statement):
            self.statements.append(statement)
            return SimpleNamespace(one_or_none=lambda: self.row)
        self.uow = SimpleNamespace(session=SimpleNamespace(execute=execute))

    def lookup(self, **kwargs):
        return SqlAlchemyIdempotencyReceipts().lookup_completed(self.uow,
            **({'scope': self.scope, 'request_fingerprint': b'f'*32} | kwargs))

    def test_select_only_scope_no_lock_no_autoflush(self):
        self.assertEqual(self.lookup(), self.result)
        statement = self.statements[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertTrue(sql.startswith('SELECT'))
        self.assertNotIn('FOR UPDATE', sql)
        for column in ('actor_id', 'project_id IS NULL', 'operation', 'key_digest'):
            self.assertIn(column, sql)
        self.assertFalse(statement.get_execution_options()['autoflush'])

    def test_absent(self):
        self.row = None
        self.assertIsNone(self.lookup())

    def test_pending_invalid_result_and_fingerprint(self):
        for row in (('PENDING', b'f'*32, None, None, None),
                    ('COMPLETED', None, self.result.ref_type, self.result.ref_id, 200),
                    ('COMPLETED', b'f'*32, 'invalid', self.result.ref_id, 200),
                    ('COMPLETED', b'f'*32, self.result.ref_type, self.result.ref_id, True)):
            self.row = row
            with self.assertRaises(IdempotencyError) as caught:
                self.lookup()
            self.assertEqual(caught.exception.code, 'SYSTEM_UNAVAILABLE')
        self.row = ('COMPLETED', b'z'*32, self.result.ref_type, self.result.ref_id, 200)
        with self.assertRaises(IdempotencyError) as caught:
            self.lookup()
        self.assertEqual(caught.exception.code, 'CONFLICT_IDEMPOTENCY')

    def test_strict_inputs_before_sql(self):
        for value in (None, bytearray(b'f'*32), b'f'*31):
            with self.assertRaises(IdempotencyError):
                self.lookup(request_fingerprint=value)
        with self.assertRaises(IdempotencyError):
            self.lookup(scope=SimpleNamespace())
        object.__setattr__(self.scope, 'operation', 'invalid')
        with self.assertRaises(IdempotencyError):
            self.lookup()
        self.assertEqual(self.statements, [])

    def test_database_error_is_static(self):
        def execute(statement):
            raise SQLAlchemyError('synthetic private driver details')
        self.uow.session.execute = execute
        with self.assertRaises(IdempotencyError) as caught:
            self.lookup()
        self.assertEqual(str(caught.exception), 'SYSTEM_UNAVAILABLE')


class ResultLookupTests(unittest.TestCase):
    def setUp(self):
        self.scope = IdempotencyScope(uuid4(), uuid4(), 'V1_EVIDENCE_SET_ELIGIBILITY', b'k'*32)
        self.result = IdempotencyResult('V1_EVIDENCE_ELIGIBILITY', uuid4(), 200)
        self.row = ('COMPLETED', self.result.ref_type, self.result.ref_id, 200)
        self.statements = []
        def execute(statement):
            self.statements.append(statement)
            return SimpleNamespace(one_or_none=lambda: self.row)
        self.uow = SimpleNamespace(session=SimpleNamespace(execute=execute))

    def lookup(self, scope=None):
        return SqlAlchemyIdempotencyReceipts().lookup_result(
            self.uow, scope=self.scope if scope is None else scope)

    def test_select_is_scoped_and_read_only(self):
        self.assertEqual(self.lookup(), self.result)
        statement = self.statements[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertTrue(sql.startswith('SELECT'))
        self.assertNotIn('FOR UPDATE', sql)
        for column in ('actor_id', 'project_id', 'operation', 'key_digest'):
            self.assertIn(column, sql)
        self.assertNotIn('request_fingerprint', sql)
        self.assertFalse(statement.get_execution_options()['autoflush'])

    def test_absent_is_inconclusive(self):
        self.row = None
        self.assertIsNone(self.lookup())

    def test_pending_or_corrupt_result_fails_closed(self):
        for row in (('PENDING', None, None, None),
                    ('COMPLETED', 'invalid', self.result.ref_id, 200),
                    ('COMPLETED', self.result.ref_type, self.result.ref_id, True)):
            self.row = row
            with self.assertRaises(IdempotencyError) as caught:
                self.lookup()
            self.assertEqual(caught.exception.code, 'SYSTEM_UNAVAILABLE')

    def test_bad_scope_and_database_error_do_not_expose_details(self):
        with self.assertRaises(IdempotencyError):
            self.lookup(scope=SimpleNamespace())
        self.assertEqual(self.statements, [])
        def execute(statement):
            raise SQLAlchemyError('synthetic private driver details')
        self.uow.session.execute = execute
        with self.assertRaises(IdempotencyError) as caught:
            self.lookup()
        self.assertEqual(str(caught.exception), 'SYSTEM_UNAVAILABLE')
