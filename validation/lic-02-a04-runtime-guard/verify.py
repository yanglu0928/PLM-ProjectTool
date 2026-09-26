"""Disposable PostgreSQL 18 runtime License Guard verification."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.license.application.license_validation import LicenseService, machine_fingerprint_hash
from plm_assistant.modules.license.application.runtime_guard import LicenseRuntimeGuard, RuntimeLicenseError
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
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
        self.calls = 0
        self.version = 0

    def current_verified_version(self):
        return self.version

    def advance(self, **kwargs):
        assert kwargs["expected_version"] == self.version
        self.calls += 1
        self.version += 1


class FailedAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic02a04_" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    valid_from, valid_to = now - timedelta(days=1), now + timedelta(days=1)
    private = Ed25519PrivateKey.generate()  # Ephemeral test key only.
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {
        "license_id": "synthetic", "customer": "synthetic",
        "machine_fingerprint": machine_fingerprint_hash("00:11:22:33:44:55").hex(),
        "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat(),
        "issue_time": (now - timedelta(days=2)).isoformat(),
        "schema_version": "plm.license.v1",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode()
    document = json.dumps({"algorithm": "Ed25519", "payload": payload,
                           "signature": base64.b64encode(private.sign(canonical)).decode()},
                          ensure_ascii=False, separators=(",", ":")).encode()
    digest = hashlib.sha256(document).digest()
    entitlement = {"product_code": "PLM_PROJECT_TOOL", "grant_scope": "FULL_BUNDLE",
                   "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat()}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                clock = Clock(now)
                trusted = TrustedTime()
                validator = LicenseService(
                    LicenseSignatureVerifier(StaticPublicKeyResolver({"synthetic-release": public})),
                    Machine(), Key(), clock, trusted,
                )
                repository = SqlAlchemyRuntimeLicenseRepository()
                audit = AuditService(SqlAlchemyAuditRepository())

                def guard(selected_audit):
                    return LicenseRuntimeGuard(
                        unit_of_work=runtime.unit_of_work, repository=repository,
                        validator=validator, trusted_time=trusted, audit=selected_audit,
                        clock=clock.now_utc,
                    )

                try:
                    guard(audit).require_valid(trace_id=uuid.uuid4())
                except RuntimeLicenseError as exc:
                    assert exc.code == "NOT_INSTALLED"
                else:
                    raise AssertionError("missing License allowed")
                with connect(name) as db:
                    user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Guard User','synthetic guard user') RETURNING user_id").fetchone()[0]
                    installation_id = db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('synthetic-release',%s,%s) RETURNING license_installation_id", (user_id, uuid.uuid4())).fetchone()[0]
                    db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (installation_id, document, digest))
                    event_id, validated_at = db.execute("INSERT INTO plm.lic_validation_events(installation_id,validation_code,machine_fingerprint_hash,document_sha256,entitlement_snapshot,trace_id,validated_at) VALUES (%s,'VALID',%s,%s,%s::jsonb,%s,%s) RETURNING validation_event_id,validated_at", (installation_id, machine_fingerprint_hash("00:11:22:33:44:55"), digest, json.dumps(entitlement), uuid.uuid4(), now)).fetchone()
                    db.execute("UPDATE plm.lic_installations SET installation_state='ACTIVE',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (event_id, installation_id))
                    db.execute("INSERT INTO plm.lic_validation_states(active_license_ref,machine_fingerprint_hash,validation_code,entitlement_snapshot,validated_at,current_event_ref,updated_at) VALUES (%s,%s,'VALID',%s::jsonb,%s,%s,%s)", (installation_id, machine_fingerprint_hash("00:11:22:33:44:55"), json.dumps(entitlement), validated_at, event_id, now))
                result = guard(audit).require_valid(trace_id=uuid.uuid4())
                assert result.grant_scope == "FULL_BUNDLE" and trusted.calls == 1
                with ThreadPoolExecutor(max_workers=2) as workers:
                    checks = [workers.submit(guard(audit).require_valid, trace_id=uuid.uuid4())
                              for _ in range(2)]
                    assert all(check.result().grant_scope == "FULL_BUNDLE" for check in checks)
                assert trusted.calls == 3
                try:
                    guard(FailedAudit()).require_valid(trace_id=uuid.uuid4())
                except RuntimeLicenseError as exc:
                    assert exc.code == "TRUST_STATE_INVALID"
                else:
                    raise AssertionError("audit failure allowed")
                clock.now = now + timedelta(days=2)
                try:
                    guard(audit).require_valid(trace_id=uuid.uuid4())
                except RuntimeLicenseError as exc:
                    assert exc.code == "EXPIRED"
                else:
                    raise AssertionError("expired License allowed")
                with connect(name) as db:
                    state = db.execute("SELECT validation_code,state_version,entitlement_snapshot FROM plm.lic_validation_states").fetchone()
                    assert state[0] == "EXPIRED" and state[1] == 4 and state[2] is None, state
                    assert db.execute("SELECT count(*) FROM plm.lic_validation_events").fetchone()[0] == 5
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_RUNTIME_CHECK'").fetchone()[0] == 4
                print("PASS: PostgreSQL real signature/machine/time chain, two-check serialization, missing/expired denial, audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
