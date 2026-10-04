"""Disposable PostgreSQL proof of real scrypt login and Session issuance."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimiter
from plm_assistant.modules.auth.application.login_service import LoginAttempt, LoginError, LoginService
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.login_identity import SqlAlchemyLoginIdentity
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.auth.infrastructure.missing_identity_verifier import ScryptMissingIdentityVerifier
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def attempt(service, username, password, expected=None):
    clear = bytearray(password)
    request = LoginAttempt(username, clear, "127.0.0.1", uuid.uuid4())
    try:
        if expected is None:
            return service.login(request)
        try:
            service.login(request)
        except LoginError as exc:
            assert exc.code == expected, (exc.code, expected)
        else:
            raise AssertionError("invalid login accepted")
    finally:
        assert clear == bytearray(len(clear))


def main():
    name = "aut03a03_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                verifier = ScryptPasswordHasher()
                raw = bytearray(b"synthetic-login-password")
                view = memoryview(raw)
                try:
                    hashed = verifier.hash_password(view)
                finally:
                    view.release()
                    raw[:] = b"\x00" * len(raw)
                with connect(name) as db:
                    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Login Owner','synthetic login owner') RETURNING user_id").fetchone()[0]
                    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id", (user, hashed.password_hash, hashed.algorithm_id, '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential, user))
                audit = AuditService(SqlAlchemyAuditRepository())
                sessions = SessionService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemySessionRepository(),
                    issue_access=SqlAlchemyPasswordIssueAccess(verifier), audit=audit,
                )
                login = LoginService(
                    unit_of_work=runtime.unit_of_work,
                    rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                          repository=SqlAlchemyLoginRateRepository()),
                    identity=SqlAlchemyLoginIdentity(),
                    missing_verifier=ScryptMissingIdentityVerifier(verifier),
                    sessions=sessions, audit=audit,
                )
                attempt(login, "unknown", b"synthetic-login-password", "AUTH_INVALID_CREDENTIALS")
                attempt(login, "Synthetic Login Owner", b"wrong-password", "AUTH_INVALID_CREDENTIALS")
                issued = attempt(login, " SYNTHETIC LOGIN OWNER ", b"synthetic-login-password")
                assert issued.user_id == user and len(issued.token) == len(issued.csrf_token) == 32
                assert sessions.validate(issued.token, csrf_token=issued.csrf_token, require_csrf=True).user_id == user
                with connect(name) as db:
                    stored = db.execute("SELECT session_token_digest,csrf_digest FROM plm.auth_sessions WHERE session_id=%s", (issued.session_id,)).fetchone()
                    assert stored == (hashlib.sha256(issued.token).digest(), hashlib.sha256(issued.csrf_token).digest())
                    actions = db.execute("SELECT action,outcome FROM plm.aud_events ORDER BY occurred_at").fetchall()
                    assert [row[0] for row in actions] == ["AUTH_LOGIN_DENIED", "AUTH_LOGIN_DENIED", "SESSION_ISSUED"]
                    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (user,))
                attempt(login, "Synthetic Login Owner", b"synthetic-login-password", "AUTH_INVALID_CREDENTIALS")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AUTH_LOGIN_DENIED'").fetchone()[0] == 3
                print("PASS: real scrypt proof, normalized identity, generic denial, Session digest/CSRF and Audit")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
