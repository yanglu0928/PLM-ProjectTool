"""Disposable PostgreSQL 18 proof of controlled License import."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.installation_import import ImportLicense, LicenseImportError, LicenseImportService
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.infrastructure.installation_import_repository import SqlAlchemyLicenseImportRepository
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Key:
    def product_key_ref(self):
        return "synthetic-release"


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic01a03_" + uuid.uuid4().hex[:12]
    token, csrf = b"a" * 32, b"b" * 32
    private = Ed25519PrivateKey.generate()  # Ephemeral test key; never persisted.
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {"schema_version": "plm.license.v1"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    document = json.dumps({"algorithm": "Ed25519", "payload": payload,
                           "signature": base64.b64encode(private.sign(canonical)).decode()},
                          separators=(",", ":")).encode()
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES ('Synthetic Admin','synthetic admin','DEPLOYMENT_ADMIN') RETURNING user_id").fetchone()[0]
                credential_id = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
                db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential_id, user_id))
                db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), user_id))
            runtime = create_database_runtime(url)
            try:
                repository = SqlAlchemyLicenseImportRepository()
                access = SqlAlchemyLicenseImportAccess()
                verifier = LicenseSignatureVerifier(StaticPublicKeyResolver({"synthetic-release": public}))
                service = LicenseImportService(
                    unit_of_work=runtime.unit_of_work, repository=repository, access=access,
                    signature=verifier, product_key=Key(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                trace = uuid.uuid4()
                result = service.import_candidate(ImportLicense(token, csrf, document, trace))
                assert result.code == "IMPORTED" and result.installation_id is not None
                try:
                    service.import_candidate(ImportLicense(token, b"c" * 32, document, uuid.uuid4()))
                except LicenseImportError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("bad CSRF was accepted")
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET deployment_role='NONE' WHERE user_id=%s", (user_id,))
                try:
                    service.import_candidate(ImportLicense(token, csrf, document, uuid.uuid4()))
                except LicenseImportError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("non-admin was accepted")
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s", (user_id,))
                bad = document.replace(b"plm.license.v1", b"plm.license.v2")
                denied = service.import_candidate(ImportLicense(token, csrf, bad, uuid.uuid4()))
                assert denied.code == "SIGNATURE_INVALID" and denied.installation_id is None
                failing = LicenseImportService(
                    unit_of_work=runtime.unit_of_work, repository=repository, access=access,
                    signature=verifier, product_key=Key(), audit=FailedAudit(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                try:
                    failing.import_candidate(ImportLicense(token, csrf, document, uuid.uuid4()))
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("audit failure was accepted")
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='TEST_REVOKED',lock_version=lock_version+1 WHERE user_id=%s", (user_id,))
                try:
                    service.import_candidate(ImportLicense(token, csrf, document, uuid.uuid4()))
                except LicenseImportError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("revoked session was accepted")
                with connect(name) as db:
                    row = db.execute("SELECT installation_state,public_key_ref,imported_by,validation_result_ref FROM plm.lic_installations").fetchone()
                    assert row == ("IMPORTED", "synthetic-release", user_id, None), row
                    assert db.execute("SELECT count(*) FROM plm.lic_installations").fetchone()[0] == 1
                    assert db.execute("SELECT signed_document,document_sha256 FROM plm.lic_installation_documents").fetchone() == (document, hashlib.sha256(document).digest())
                    assert db.execute("SELECT count(*) FROM plm.lic_validation_events WHERE validation_code='SIGNATURE_INVALID' AND installation_id IS NULL").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_IMPORT'").fetchone()[0] == 2
                print("PASS: PostgreSQL admin/CSRF/revocation proof, immutable import, safe rejection and audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
