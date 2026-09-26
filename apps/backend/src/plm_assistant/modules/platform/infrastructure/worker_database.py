"""Explicit Worker-only PG18 limits; ordinary HTTP runtime defaults unchanged."""
from contextlib import contextmanager
from dataclasses import dataclass
from sqlalchemy import text
from .database import DatabaseEngineOptions, create_database_runtime


@dataclass(frozen=True, slots=True)
class WorkerDatabaseLimits:
    lock_timeout_ms: int = 1000
    statement_timeout_ms: int = 2000
    transaction_timeout_ms: int = 5000
    pool_timeout_seconds: int = 2
    connect_timeout_seconds: int = 2
    pool_size: int = 4
    max_overflow: int = 0

    def __post_init__(self):
        for value in (self.lock_timeout_ms,self.statement_timeout_ms,self.transaction_timeout_ms):
            if type(value) is not int or not 1 <= value <= 60000:
                raise ValueError('Invalid Worker database timeout')
        if not self.lock_timeout_ms < self.statement_timeout_ms < self.transaction_timeout_ms:
            raise ValueError('Worker timeout order required')
        for value in (self.pool_timeout_seconds,self.connect_timeout_seconds):
            if type(value) is not int or not 1 <= value <= 10:
                raise ValueError('Invalid Worker connection timeout')
        if (type(self.pool_size) is not int or not 1 <= self.pool_size <= 20
                or type(self.max_overflow) is not int or not 0 <= self.max_overflow <= 20):
            raise ValueError('Invalid Worker database pool bounds')


class WorkerDatabaseRuntime:
    def __init__(self, *, runtime, limits):
        if runtime is None or type(limits) is not WorkerDatabaseLimits:
            raise ValueError('Worker runtime and strict limits required')
        limits.__post_init__()
        self._runtime,self._limits=runtime,limits

    @contextmanager
    def unit_of_work(self):
        with self._runtime.unit_of_work() as tx:
            connection=tx.session.connection()
            if connection.dialect.name != 'postgresql' or connection.dialect.server_version_info[:1] != (18,):
                raise RuntimeError('Worker database unavailable')
            values=dict(lock_timeout=self._limits.lock_timeout_ms,
                        statement_timeout=self._limits.statement_timeout_ms,
                        transaction_timeout=self._limits.transaction_timeout_ms)
            tx.session.execute(text("SELECT set_config('lock_timeout',:lock,true), "
                "set_config('statement_timeout',:statement,true), set_config('transaction_timeout',:transaction,true)"),
                dict(lock=str(values['lock_timeout'])+'ms',statement=str(values['statement_timeout'])+'ms',
                     transaction=str(values['transaction_timeout'])+'ms'))
            actual={name:int(value) for name,value in tx.session.execute(text(
                "SELECT name,setting FROM pg_settings WHERE name IN ('lock_timeout','statement_timeout','transaction_timeout')"))}
            if actual != values:
                raise RuntimeError('Worker database unavailable')
            yield tx

    def is_ready(self):
        try:
            with self.unit_of_work() as tx:
                return tx.session.scalar(text('SELECT 1')) == 1
        except Exception:
            return False

    def dispose(self):
        self._runtime.dispose()


def create_worker_database_runtime(database_url, *, limits=None):
    limits=limits if limits is not None else WorkerDatabaseLimits()
    if type(limits) is not WorkerDatabaseLimits:
        raise ValueError('Strict Worker limits required')
    limits.__post_init__()
    runtime=create_database_runtime(database_url,options=DatabaseEngineOptions(
        pool_size=limits.pool_size,max_overflow=limits.max_overflow,
        pool_timeout_seconds=limits.pool_timeout_seconds,connect_timeout_seconds=limits.connect_timeout_seconds))
    return WorkerDatabaseRuntime(runtime=runtime,limits=limits)
