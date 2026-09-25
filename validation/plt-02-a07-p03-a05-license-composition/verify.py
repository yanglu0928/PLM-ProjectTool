"""Disposable Windows/PostgreSQL composition check; synthetic signing key only."""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import tempfile
import uuid
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.windows_license_runtime import _assemble
from plm_assistant.modules.license.application.license_validation import machine_fingerprint_hash
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.license.infrastructure.packaged_product_key import (
    PRODUCT_CODE, PRODUCT_KEY_REF, PackagedProductKey,
)
from plm_assistant.modules.license.infrastructure.trusted_time_integrity import HmacTrustedTimeIntegrity
from plm_assistant.modules.license.infrastructure.windows_selected_machine import (
    WindowsSelectedMachine, windows_local_macs,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import provision_new
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def _connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main() -> None:
    name = "plt02a07_" + uuid.uuid4().hex[:12]
    key_ref = "test-license-time-" + uuid.uuid4().hex
    target = "PLMProjectTool/SecretKey/" + key_ref
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    library.CredDeleteW.restype = wintypes.BOOL
    provider = WindowsSecretKeyProvider()
    selected = sorted(windows_local_macs())[0]
    machine = WindowsSelectedMachine(selected)
    private = Ed25519PrivateKey.generate()  # Process-only synthetic fixture.
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    manifest = json.dumps({
        "schema_version": "plm.product-public-key.v1",
        "product_code": PRODUCT_CODE, "key_ref": PRODUCT_KEY_REF,
        "public_key": base64.b64encode(public).decode("ascii"),
    }, sort_keys=True, separators=(",", ":")).encode("ascii")
    product = PackagedProductKey(read_manifest=lambda: manifest)
    with tempfile.TemporaryDirectory() as directory, _connect("postgres") as admin:
        backup = Path(directory) / "synthetic-time-key.json"
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            provision_new(key_ref=key_ref, backup_path=backup,
                          passphrase="synthetic-only-composition-passphrase", provider=provider)
            integrity = HmacTrustedTimeIntegrity(provider, key_ref=key_ref)
            url = URL.create("postgresql+psycopg", username=USER,
                             host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            services = _assemble(runtime, product=product, machine=machine, integrity=integrity)
            try:
                services.guard.require_valid(trace_id=uuid.uuid4())
            except RuntimeLicenseError as exc:
                assert exc.code == "NOT_INSTALLED", exc.code
            else:
                raise AssertionError("missing License allowed")
            now = datetime.now(timezone.utc)
            valid_from, valid_to = now - timedelta(days=1), now + timedelta(days=1)
            payload = {
                "license_id": "synthetic-composition", "customer": "synthetic-only",
                "machine_fingerprint": machine_fingerprint_hash(selected).hex(),
                "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat(),
                "issue_time": (now - timedelta(days=2)).isoformat(),
                "schema_version": "plm.license.v1",
            }
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")
            document = json.dumps({
                "algorithm": "Ed25519", "payload": payload,
                "signature": base64.b64encode(private.sign(canonical)).decode("ascii"),
            }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(document).digest()
            entitlement = {
                "product_code": PRODUCT_CODE, "grant_scope": "FULL_BUNDLE",
                "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat(),
            }
            with _connect(name) as db:
                db.execute("INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES")
                user_id = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Composition User','synthetic composition user') RETURNING user_id"
                ).fetchone()[0]
                installation_id = db.execute(
                    "INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) "
                    "VALUES (%s,%s,%s) RETURNING license_installation_id",
                    (PRODUCT_KEY_REF, user_id, uuid.uuid4()),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.lic_installation_documents"
                    "(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)",
                    (installation_id, document, digest),
                )
                event_id, validated_at = db.execute(
                    "INSERT INTO plm.lic_validation_events"
                    "(installation_id,validation_code,machine_fingerprint_hash,document_sha256,"
                    "entitlement_snapshot,trace_id,validated_at) "
                    "VALUES (%s,'VALID',%s,%s,%s::jsonb,%s,%s) "
                    "RETURNING validation_event_id,validated_at",
                    (installation_id, machine_fingerprint_hash(selected), digest,
                     json.dumps(entitlement), uuid.uuid4(), now),
                ).fetchone()
                db.execute(
                    "UPDATE plm.lic_installations SET installation_state='ACTIVE',"
                    "validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s",
                    (event_id, installation_id),
                )
                db.execute(
                    "INSERT INTO plm.lic_validation_states"
                    "(active_license_ref,machine_fingerprint_hash,validation_code,"
                    "entitlement_snapshot,validated_at,current_event_ref,updated_at) "
                    "VALUES (%s,%s,'VALID',%s::jsonb,%s,%s,%s)",
                    (installation_id, machine_fingerprint_hash(selected),
                     json.dumps(entitlement), validated_at, event_id, now),
                )
            verified = services.guard.require_valid(trace_id=uuid.uuid4())
            assert verified.grant_scope == "FULL_BUNDLE"
            assert services.trusted_time.current_verified_version() == 1
            assert library.CredDeleteW(target, 1, 0)
            try:
                services.guard.require_valid(trace_id=uuid.uuid4())
            except RuntimeLicenseError as exc:
                assert exc.code == "TRUST_STATE_INVALID", exc.code
            else:
                raise AssertionError("missing trusted-time key allowed")
            with _connect(name) as db:
                code = db.execute(
                    "SELECT validation_code FROM plm.lic_validation_states"
                ).fetchone()[0]
                assert code == "TRUST_STATE_INVALID", code
            print("PASS: real PostgreSQL, local MAC, synthetic signed License, "
                  "Vault HMAC, audited missing-key denial")
        finally:
            if runtime is not None:
                runtime.dispose()
            library.CredDeleteW(target, 1, 0)
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
