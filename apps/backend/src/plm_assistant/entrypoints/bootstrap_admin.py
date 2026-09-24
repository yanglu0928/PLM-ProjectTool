"""Local interactive first-admin setup; never accepts credentials as CLI arguments."""

from __future__ import annotations

import getpass
import hmac
import sys
import uuid
import warnings

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.initial_admin import (
    InitializeAdmin, InitialAdminService,
)
from plm_assistant.modules.auth.infrastructure.initial_admin import SqlAlchemyInitialAdminRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime


def _hidden(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def main() -> int:
    if len(sys.argv) != 1 or not sys.stdin.isatty():
        print("Interactive local terminal required; no credential arguments are accepted.", file=sys.stderr)
        return 2
    password = bytearray()
    confirmation = bytearray()
    runtime = None
    try:
        database_url = _hidden("Database URL (hidden): ")
        username = input("Initial admin username: ")
        password = bytearray(_hidden("Initial admin password (hidden): ").encode("utf-8"))
        confirmation = bytearray(_hidden("Confirm password (hidden): ").encode("utf-8"))
        if not hmac.compare_digest(password, confirmation):
            print("Passwords do not match.", file=sys.stderr)
            return 2
        runtime = create_database_runtime(database_url)
        service = InitialAdminService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyInitialAdminRepository(),
            hasher=ScryptPasswordHasher(),
            audit=AuditService(SqlAlchemyAuditRepository()),
        )
        service.initialize(InitializeAdmin(username, password, uuid.uuid4()))
        print("Initial administrator created. Store the credentials securely.")
        return 0
    except Exception:
        print("Initialization rejected or unavailable; no credentials were printed.", file=sys.stderr)
        return 1
    finally:
        password[:] = b"\x00" * len(password)
        confirmation[:] = b"\x00" * len(confirmation)
        if runtime is not None:
            runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
