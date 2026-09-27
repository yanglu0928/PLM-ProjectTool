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
