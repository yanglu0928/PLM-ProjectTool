"""Disposable PostgreSQL 18 end-to-end check of internal full-bundle License verification."""

from __future__ import annotations

import base64
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
from plm_assistant.modules.license.application.license_validation import LicenseService, LicenseValidationError, machine_fingerprint_hash
from plm_assistant.modules.license.application.signature_verifier import LicenseSignatureVerifier
from plm_assistant.modules.license.application.trusted_time import TrustedTimeStatePort
from plm_assistant.modules.license.infrastructure.static_public_keys import StaticPublicKeyResolver
from plm_assistant.modules.license.infrastructure.trusted_time_integrity import HmacTrustedTimeIntegrity
from plm_assistant.modules.license.infrastructure.trusted_time_repository import SqlAlchemyTrustedTimeRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
KEY_REF = "plm-project-tool-test-release"
MAC = "00:11:22:33:44:55"


class Machine:
    def __init__(self):
        self.mac = MAC

    def selected_mac(self):
        return self.mac


class ProductKey:
    def product_key_ref(self):
        return KEY_REF


class Clock:
    def __init__(self, now):
        self.now = now

    def now_utc(self):
        return self.now


class IntegrityKey:
    def resolve_key(self, key_ref):
        return b"synthetic-integrity-key-not-for-production" if key_ref == "synthetic-integrity" else None


def signed(private, payload):
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return json.dumps({"algorithm": "Ed25519", "payload": payload,
                       "signature": base64.b64encode(private.sign(canonical)).decode("ascii")},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def reject(fn, code):
    try:
        fn()
    except LicenseValidationError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"unsafe License accepted: {code}")


def main():
    name = f"lic02a02_{uuid.uuid4().hex[:12]}"
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    with psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            with psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True) as db:
                db.execute("INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES")
            private = Ed25519PrivateKey.generate()  # in-memory synthetic test key; never saved
            public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            now = datetime.now(timezone.utc) + timedelta(seconds=3)
            payload = {
                "license_id": "synthetic-integration-license", "customer": "合成测试客户",
                "machine_fingerprint": machine_fingerprint_hash(MAC).hex(),
                "valid_from": (now - timedelta(days=1)).isoformat(),
                "valid_to": (now + timedelta(days=1)).isoformat(),
                "issue_time": (now - timedelta(days=2)).isoformat(),
                "schema_version": "plm.license.v1",
            }
            document = signed(private, payload)
            machine, clock = Machine(), Clock(now)
            trusted = TrustedTimeStatePort(runtime.unit_of_work, SqlAlchemyTrustedTimeRepository(),
                                           HmacTrustedTimeIntegrity(IntegrityKey(), key_ref="synthetic-integrity"),
                                           AuditService(SqlAlchemyAuditRepository()))
            service = LicenseService(LicenseSignatureVerifier(StaticPublicKeyResolver({KEY_REF: public})),
                                     machine, ProductKey(), clock, trusted)
            result = service.validate(document, expected_time_version=0, trace_id=uuid.uuid4())
            assert result.grant_scope == "FULL_BUNDLE" and result.product_code == "PLM_PROJECT_TOOL"
            reject(lambda: service.validate(document, expected_time_version=0, trace_id=uuid.uuid4()), "TRUST_STATE_INVALID")
            machine.mac = "00:11:22:33:44:56"
            reject(lambda: service.validate(document, expected_time_version=1, trace_id=uuid.uuid4()), "MACHINE_MISMATCH")
            machine.mac = MAC
            clock.now = now - timedelta(minutes=10)
            reject(lambda: service.validate(document, expected_time_version=1, trace_id=uuid.uuid4()), "TIME_ROLLBACK")
            with psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True) as db:
                assert db.execute("SELECT state_version FROM plm.lic_trusted_time_states").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.lic_validation_states").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_TRUSTED_TIME_CHECK'").fetchone()[0] == 3
            print("PASS: real Ed25519 + seven-field schema + selected MAC + validity + trusted-time PostgreSQL, stale version/mismatch/rollback denied; no activation or validation-state write")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
