from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker


POSTGRESQL_DRIVER = "postgresql+psycopg"


class DatabaseConfigurationError(ValueError):
    """Raised when the composition root provides an unsafe database setting."""


class UnitOfWorkStateError(RuntimeError):
    """Raised when a unit of work is used outside its single transaction scope."""


@dataclass(frozen=True, slots=True)
class DatabaseEngineOptions:
    """Non-secret engine settings; credentials remain in the SQLAlchemy URL."""

    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 1_800
    connect_timeout_seconds: int = 5

    def __post_init__(self) -> None:
        positive_values = {
            "pool_size": self.pool_size,
            "pool_timeout_seconds": self.pool_timeout_seconds,
            "pool_recycle_seconds": self.pool_recycle_seconds,
            "connect_timeout_seconds": self.connect_timeout_seconds,
        }
        for name, value in positive_values.items():
            if value <= 0:
                raise DatabaseConfigurationError(f"{name} must be greater than zero")
        if self.max_overflow < 0:
            raise DatabaseConfigurationError("max_overflow must not be negative")


class SqlAlchemyUnitOfWork:
    """One-shot SQLAlchemy session with explicit commit and fail-safe rollback."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._transaction: SessionTransaction | None = None
        self._finished = False
        self._used = False

    @property
    def session(self) -> Session:
        if self._session is None:
            raise UnitOfWorkStateError("unit of work is not active")
        return self._session

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._used:
            raise UnitOfWorkStateError("unit of work instances are single-use")
        self._used = True
        session = self._session_factory()
        try:
            transaction = session.begin()
        except BaseException:
            session.close()
            raise
        self._session = session
        self._transaction = transaction
        return self

    def commit(self) -> None:
        transaction = self._active_transaction()
        transaction.commit()
        self._finished = True

    def rollback(self) -> None:
        transaction = self._active_transaction()
        transaction.rollback()
        self._finished = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        session = self._session
        transaction = self._transaction
        if session is None or transaction is None:
            raise UnitOfWorkStateError("unit of work is not active")
        try:
            if not self._finished and transaction.is_active:
                try:
                    transaction.rollback()
                except BaseException:
                    if exc_type is None:
                        raise
        finally:
            session.close()
            self._session = None
            self._transaction = None
        return False

    def _active_transaction(self) -> SessionTransaction:
        if self._session is None or self._transaction is None:
            raise UnitOfWorkStateError("unit of work is not active")
        if self._finished or not self._transaction.is_active:
            raise UnitOfWorkStateError("unit of work transaction is already complete")
        return self._transaction


class DatabaseRuntime:
    """Own the process-local engine and create isolated transaction scopes."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session_factory = sessionmaker(
            bind=engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
            autobegin=False,
        )

    @property
    def safe_url(self) -> str:
        return self._engine.url.render_as_string(hide_password=True)

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    def is_ready(self) -> bool:
        try:
            with self._engine.connect() as connection:
                return connection.scalar(text("SELECT 1")) == 1
        except SQLAlchemyError:
            return False

    def dispose(self) -> None:
        self._engine.dispose()

    def __repr__(self) -> str:
        return f"DatabaseRuntime(url={self.safe_url!r})"


def create_database_runtime(
    database_url: str | URL,
    *,
    options: DatabaseEngineOptions | None = None,
) -> DatabaseRuntime:
    """Build the PostgreSQL runtime without reading environment or secret files."""

    url = validate_database_url(database_url)

    engine_options = options or DatabaseEngineOptions()
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=engine_options.pool_size,
        max_overflow=engine_options.max_overflow,
        pool_timeout=engine_options.pool_timeout_seconds,
        pool_recycle=engine_options.pool_recycle_seconds,
        pool_reset_on_return="rollback",
        isolation_level="READ COMMITTED",
        connect_args={
            "connect_timeout": engine_options.connect_timeout_seconds,
            "application_name": "plm-project-tool",
        },
        hide_parameters=True,
    )
    return DatabaseRuntime(engine)


def validate_database_url(database_url: str | URL) -> URL:
    """Return a validated PostgreSQL URL without rendering its credentials."""

    url = make_url(database_url) if isinstance(database_url, str) else database_url
    if url.drivername != POSTGRESQL_DRIVER:
        raise DatabaseConfigurationError(
            f"database driver must be {POSTGRESQL_DRIVER!r}"
        )
    if not url.database:
        raise DatabaseConfigurationError("database name is required")
    return url
