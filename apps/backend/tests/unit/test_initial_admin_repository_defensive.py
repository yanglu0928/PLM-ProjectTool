import unittest
from types import SimpleNamespace
from sqlalchemy.orm import Session
from plm_assistant.modules.auth.infrastructure.initial_admin import SqlAlchemyInitialAdminRepository
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


class InitialAdminRepositoryDefensiveTests(unittest.TestCase):
    def setUp(self):
        self.repo = SqlAlchemyInitialAdminRepository()

    def _call(self, transaction, operation):
        if operation == 'claim':
            return self.repo.claim_empty(transaction)
        return self.repo.create(transaction, username_display='Synthetic admin',
                                username_normalized='synthetic admin',
                                hashed=PasswordHashResult('UNIT_ONLY', 'SCRYPT', {'n':131072}))

    def test_wrong_and_real_inactive_sources_never_begin_transaction(self):
        with Session() as inactive:
            for source in (None, object(), inactive):
                for operation in ('claim', 'create'):
                    with self.subTest(source_type=type(source).__name__, operation=operation):
                        with self.assertRaisesRegex(RuntimeError, '^active bootstrap transaction is required$'):
                            self._call(SimpleNamespace(session=source), operation)
                        self.assertFalse(inactive.in_transaction())

    def test_missing_session_preserves_original_attribute_error(self):
        for source in (None, SimpleNamespace(), object()):
            for operation in ('claim', 'create'):
                with self.subTest(source_type=type(source).__name__, operation=operation), self.assertRaises(AttributeError):
                    self._call(source, operation)

    def test_session_source_exception_propagates_without_sql(self):
        class FaultSource:
            @property
            def session(self):
                raise RuntimeError('Synthetic source fault')
        for operation in ('claim', 'create'):
            with self.subTest(operation=operation), self.assertRaisesRegex(RuntimeError, '^Synthetic source fault$'):
                self._call(FaultSource(), operation)
