"""Disposable PostgreSQL verification of controlled License recovery."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.license_validation import LicenseService, machine_fingerprint_hash
from plm_assistant.modules.license.application.revalidation import (
    LicenseRevalidationError, LicenseRevalidationService, RevalidateLicense,
)
from plm_assistant.modules.license.application.runtime_guard import LicenseRuntimeGuard, RuntimeLicenseError
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.infrastructure.revalidation_repository import SqlAlchemyLicenseRecoveryRepository
from plm_assistant.modules.license.infrastructure.runtime_guard_repository import SqlAlchemyRuntimeLicenseRepository
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Machine:
    def selected_mac(self):
        return "00:11:22:33:44:55"


class Key:
    def product_key_ref(self):
        return "synthetic-release"


class Clock:
    def __init__(self, now):
        self.now = now

    def now_utc(self):
        return self.now


class TrustedTime:
    def __init__(self):
        self.version = 0
        self.broken = False

    def current_verified_version(self):
        if self.broken:
            raise RuntimeError("synthetic integrity failure")
        return self.version

    def advance(self, **kwargs):
        assert kwargs["expected_version"] == self.version
        self.version += 1


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic02a05_" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    valid_from, valid_to = now - timedelta(days=1), now + timedelta(days=1)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {
        "license_id": "synthetic", "customer": "synthetic",
        "machine_fingerprint": machine_fingerprint_hash("00:11:22:33:44:55").hex(),
        "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat(),
        "issue_time": (now - timedelta(days=2)).isoformat(),
        "schema_version": "plm.license.v1",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    document = json.dumps({"algorithm": "Ed25519", "payload": payload,
                           "signature": base64.b64encode(private.sign(canonical)).decode()},
                          ensure_ascii=False, separators=(",", ":")).encode()
    digest = hashlib.sha256(document).digest()
    entitlement = {"product_code": "PLM_PROJECT_TOOL", "grant_scope": "FULL_BUNDLE",
                   "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat()}
    token, csrf = b"s" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                clock, trusted = Clock(now), TrustedTime()
                validator = LicenseService(
                    LicenseSignatureVerifier(StaticPublicKeyResolver({"synthetic-release": public})),
                    Machine(), Key(), clock, trusted,
                )
                audit = AuditService(SqlAlchemyAuditRepository())
                with connect(name) as db:
                    user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES ('Synthetic Recovery Admin','synthetic recovery admin','DEPLOYMENT_ADMIN') RETURNING user_id").fetchone()[0]
                    credential_id = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential_id, user_id))
                    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), user_id))
                    installation_id = db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('synthetic-release',%s,%s) RETURNING license_installation_id", (user_id, uuid.uuid4())).fetchone()[0]
                    db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (installation_id, document, digest))
                    event_id, validated_at = db.execute("INSERT INTO plm.lic_validation_events(installation_id,validation_code,machine_fingerprint_hash,document_sha256,entitlement_snapshot,trace_id,validated_at) VALUES (%s,'VALID',%s,%s,%s::jsonb,%s,%s) RETURNING validation_event_id,validated_at", (installation_id, machine_fingerprint_hash("00:11:22:33:44:55"), digest, json.dumps(entitlement), uuid.uuid4(), now)).fetchone()
                    db.execute("UPDATE plm.lic_installations SET installation_state='ACTIVE',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (event_id, installation_id))
                    db.execute("INSERT INTO plm.lic_validation_states(active_license_ref,machine_fingerprint_hash,validation_code,entitlement_snapshot,validated_at,current_event_ref,updated_at) VALUES (%s,%s,'VALID',%s::jsonb,%s,%s,%s)", (installation_id, machine_fingerprint_hash("00:11:22:33:44:55"), json.dumps(entitlement), validated_at, event_id, now))

                guard = LicenseRuntimeGuard(unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyRuntimeLicenseRepository(), validator=validator,
                    trusted_time=trusted, audit=audit, clock=clock.now_utc)
                def service(selected_audit):
                    return LicenseRevalidationService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyLicenseImportAccess(),
                        repository=SqlAlchemyLicenseRecoveryRepository(),
                        validator=validator, trusted_time=trusted,
                        audit=selected_audit, clock=lambda: datetime.now(timezone.utc),
                    )
                def recovery_command():
                    return RevalidateLicense(token, csrf, uuid.uuid4())

                clock.now = now + timedelta(days=2)
                try:
                    guard.require_valid(trace_id=uuid.uuid4())
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("expired license allowed")
                clock.now = now
                recovered = service(audit).revalidate_active(recovery_command())
                assert recovered.code == "VALID" and recovered.state_version == 2
                assert guard.require_valid(trace_id=uuid.uuid4()).grant_scope == "FULL_BUNDLE"
                with connect(name) as db:
                    before = db.execute("SELECT state_version,current_event_ref FROM plm.lic_validation_states").fetchone()
                try:
                    service(audit).revalidate_active(RevalidateLicense(token, b"x" * 32, uuid.uuid4()))
                except LicenseRevalidationError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("invalid CSRF allowed")
                with connect(name) as db:
                    assert db.execute("SELECT state_version,current_event_ref FROM plm.lic_validation_states").fetchone() == before
                try:
                    service(FailedAudit()).revalidate_active(recovery_command())
                except LicenseRevalidationError as exc:
                    assert exc.code == "TRUST_STATE_INVALID"
                else:
                    raise AssertionError("audit failure allowed")
                with connect(name) as db:
                    assert db.execute("SELECT state_version,current_event_ref FROM plm.lic_validation_states").fetchone() == before
                clock.now = now + timedelta(days=2)
                try:
                    service(audit).revalidate_active(recovery_command())
                except LicenseRevalidationError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("expired revalidation allowed")
                with connect(name) as db:
                    state = db.execute("SELECT validation_code,entitlement_snapshot FROM plm.lic_validation_states").fetchone()
                    assert state == ("EXPIRED", None), state
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_REVALIDATED'").fetchone()[0] == 2
                trusted.broken = True
                try:
                    service(audit).revalidate_active(recovery_command())
                except LicenseRevalidationError as exc:
                    assert exc.code == "TRUST_STATE_INVALID"
                else:
                    raise AssertionError("trusted-time failure allowed")
                with connect(name) as db:
                    assert db.execute("SELECT validation_code FROM plm.lic_validation_states").fetchone()[0] == "TRUST_STATE_INVALID"
                print("PASS: PostgreSQL recovery from denial, real Ed25519 validation, CSRF denial, expired and trusted-time denial, audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
