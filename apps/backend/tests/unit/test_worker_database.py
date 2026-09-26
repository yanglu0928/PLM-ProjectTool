from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch
from plm_assistant.modules.platform.infrastructure.database import DatabaseEngineOptions
from plm_assistant.modules.platform.infrastructure.worker_database import (
    WorkerDatabaseLimits,WorkerDatabaseRuntime,create_worker_database_runtime,
)


class WorkerDatabaseTests(TestCase):
    def setUp(self):
        self.limits=WorkerDatabaseLimits()
        self.runtime,self.tx=Mock(),Mock()
        self.runtime.unit_of_work.return_value=MagicMock()
        self.runtime.unit_of_work.return_value.__enter__.return_value=self.tx
        connection=self.tx.session.connection.return_value
        connection.dialect.name='postgresql';connection.dialect.server_version_info=(18,6)
        self.tx.session.execute.side_effect=[None,[('lock_timeout','1000'),('statement_timeout','2000'),('transaction_timeout','5000')]]

    def test_opt_in_exact_local_settings_no_commit(self):
        worker=WorkerDatabaseRuntime(runtime=self.runtime,limits=self.limits)
        with worker.unit_of_work() as actual:self.assertIs(actual,self.tx)
        self.assertIn('set_config',str(self.tx.session.execute.call_args_list[0].args[0]))
        self.assertEqual(self.tx.session.execute.call_args_list[0].args[1],dict(lock='1000ms',statement='2000ms',transaction='5000ms'))
        self.tx.commit.assert_not_called()
        self.runtime.unit_of_work.return_value.__exit__.assert_called_once()

    def test_strict_limits_and_ordinary_defaults_unchanged(self):
        for changes in (dict(lock_timeout_ms=True),dict(statement_timeout_ms=0),dict(transaction_timeout_ms=60001),
                        dict(lock_timeout_ms=2000),dict(pool_timeout_seconds=11),dict(connect_timeout_seconds=True),
                        dict(pool_size=0),dict(max_overflow=True)):
            with self.assertRaises(ValueError):replace(self.limits,**changes)
        self.assertEqual(DatabaseEngineOptions().pool_timeout_seconds,30)
        with patch('plm_assistant.modules.platform.infrastructure.worker_database.create_database_runtime',return_value=self.runtime) as factory:
            create_worker_database_runtime('postgresql+psycopg://localhost/synthetic')
        options=factory.call_args.kwargs['options']
        self.assertEqual((options.pool_size,options.max_overflow,options.pool_timeout_seconds,options.connect_timeout_seconds),(4,0,2,2))

    def test_unsupported_database_or_ineffective_limits_fails_closed(self):
        worker=WorkerDatabaseRuntime(runtime=self.runtime,limits=self.limits)
        self.tx.session.connection.return_value.dialect.server_version_info=(17,6)
        with self.assertRaises(RuntimeError):
            with worker.unit_of_work():pass
        self.tx.session.connection.return_value.dialect.server_version_info=(18,6)
        self.tx.session.execute.side_effect=[None,[('lock_timeout','0')]]
        with self.assertRaises(RuntimeError):
            with worker.unit_of_work():pass
        self.tx.commit.assert_not_called()

    def test_readiness_failure_and_dispose_owned_runtime(self):
        worker=WorkerDatabaseRuntime(runtime=self.runtime,limits=self.limits)
        self.tx.session.connection.side_effect=RuntimeError('synthetic private URL')
        self.assertFalse(worker.is_ready());worker.dispose();self.runtime.dispose.assert_called_once()
