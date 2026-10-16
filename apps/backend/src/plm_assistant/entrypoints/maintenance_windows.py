"""Interactive current-account Windows maintenance switch; not a backup permit."""

from __future__ import annotations

import getpass
import sys
import uuid
import warnings
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimiter
from plm_assistant.modules.auth.application.login_service import LoginAttempt, LoginService
from plm_assistant.modules.auth.application.session_service import SessionPolicy, SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.login_identity import SqlAlchemyLoginIdentity
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.auth.infrastructure.missing_identity_verifier import ScryptMissingIdentityVerifier
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime, create_database_runtime
from plm_assistant.modules.platform.infrastructure.maintenance_transition import (
    MaintenanceTransitionReceipt, PostgresMaintenanceTransition,
)
from plm_assistant.modules.platform.infrastructure.windows_database_credential import read_database_url


class MaintenanceCommandError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("maintenance command rejected or outcome uncertain")


def execute_maintenance(*, runtime: DatabaseRuntime, engine: Engine,
                        username: str, password: bytearray, target: str,
                        expected_version: int) -> MaintenanceTransitionReceipt:
    """No credential token leaves this process; caller must own an interactive OS account."""
    issued = None
    receipt = None
    sessions = None
    try:
        if (not isinstance(runtime, DatabaseRuntime) or not isinstance(engine, Engine)
                or type(username) is not str or not username
                or type(password) is not bytearray or not password
                or target not in ("RUNNING", "MAINTENANCE")
                or type(expected_version) is not int or expected_version < 0):
            raise MaintenanceCommandError()
        audit = AuditService(SqlAlchemyAuditRepository())
        verifier = ScryptPasswordHasher()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(verifier),
            audit=audit,
            policy=SessionPolicy(absolute_lifetime=timedelta(minutes=5),
                                 idle_lifetime=timedelta(minutes=5)),
        )
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyLoginRateRepository()),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(verifier),
            sessions=sessions, audit=audit,
        )
        issued = login.login(LoginAttempt(username, password, "127.0.0.1", uuid.uuid4()))
        receipt = PostgresMaintenanceTransition(
            engine, access=SqlAlchemyLicenseImportAccess(),
        ).change(target=target, expected_version=expected_version,
                 session_token=issued.token, csrf_token=issued.csrf_token)
    except Exception:
        raise MaintenanceCommandError() from None
    finally:
        password[:] = b"\x00" * len(password)
        if issued is not None and sessions is not None:
            try:
                sessions.revoke(token=issued.token, csrf_token=issued.csrf_token,
                                trace_id=uuid.uuid4())
            except Exception:
                raise MaintenanceCommandError() from None
    assert receipt is not None
    return receipt


def _hidden_password() -> bytearray:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return bytearray(getpass.getpass("Admin password (hidden): ").encode("utf-8"))


def main() -> int:
    if (sys.platform != "win32" or not sys.stdin.isatty()
            or not sys.stdout.isatty() or len(sys.argv) != 3
            or sys.argv[1] not in ("enter", "exit")
            or not sys.argv[2].isascii() or not sys.argv[2].isdecimal()
            or len(sys.argv[2]) > 19):
        print("Usage (local interactive Windows account only): "
              "python -m plm_assistant.entrypoints.maintenance_windows "
              "{enter|exit} <expected-version>", file=sys.stderr)
        return 2
    target = "MAINTENANCE" if sys.argv[1] == "enter" else "RUNNING"
    runtime = engine = None
    password = bytearray()
    try:
        # Only the invoking Windows logon account's credential is reachable.
        url = read_database_url()
        runtime = create_database_runtime(url)
        engine = create_engine(url, pool_size=2, max_overflow=0,
                               pool_timeout=2, pool_pre_ping=True,
                               connect_args={"connect_timeout": 2},
                               hide_parameters=True)
        username = input("Current deployment admin username: ")
        password = _hidden_password()
        receipt = execute_maintenance(
            runtime=runtime, engine=engine, username=username, password=password,
            target=target, expected_version=int(sys.argv[2]),
        )
        print(f"State: {receipt.state}; version: {receipt.lock_version}. "
              "This does not certify process quiescence or permit backup/migration.")
        return 0
    except Exception:
        print("Maintenance command rejected or outcome uncertain. "
              "Inspect persisted state and Audit before retrying.", file=sys.stderr)
        return 1
    finally:
        password[:] = b"\x00" * len(password)
        if engine is not None:
            engine.dispose()
        if runtime is not None:
            runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
