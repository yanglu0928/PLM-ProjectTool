"""PostgreSQL 18 integration for the PLG-01-A07 atomic registration owner."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import uuid
import zipfile
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import URL, text
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
from plm_assistant.modules.plugin.application.package_archive_inspector import PluginPackageArchiveInspector
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageCompatibilityAssessment,
    PluginPackageRegistrationError,
    PluginPackageRegistrationService,
    RegisterPluginPackageCommand,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    TrustedPluginSigner,
)
from plm_assistant.modules.plugin.infrastructure.package_registration_repository import (
    SqlAlchemyPluginPackageRegistrationRepository,
)


_KEY_REF = "synthetic-a07-integration-key"


def _url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                      port=port, database=name)


def _dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE postgres").format(sql.Identifier(name)))


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


class _Resolver:
    def __init__(self, public_key: bytes) -> None:
        self.public_key = public_key

    def resolve_trusted_signer(self, signer_key_ref: str):
        if signer_key_ref != _KEY_REF:
            return None
        return TrustedPluginSigner(_KEY_REF, self.public_key)


class _Compatibility:
    def __init__(self, compatible: bool = True) -> None:
        self.compatible = compatible

    def evaluate(self, _manifest: object, *, policy_ref: str):
        if policy_ref != "synthetic.win11.v1":
            return PluginPackageCompatibilityAssessment(False, "PLUGIN_OS_INCOMPATIBLE")
        if not self.compatible:
            return PluginPackageCompatibilityAssessment(False, "PLUGIN_OS_INCOMPATIBLE")
        return PluginPackageCompatibilityAssessment(True)


def _diagnostic(stage: str, call, *args: object, **kwargs: object):
    try:
        return call(*args, **kwargs)
    except Exception as exc:
        print("A07_DIAGNOSTIC " + json.dumps({
            "stage": stage,
            "exception_type": type(exc).__name__,
            "sqlstate": getattr(exc, "sqlstate", None),
        }, sort_keys=True), file=sys.stderr)
        raise


class _DiagnosticRepository:
    def __init__(self, inner: SqlAlchemyPluginPackageRegistrationRepository) -> None:
        self.inner = inner

    def lock_identity(self, *args: object, **kwargs: object) -> None:
        _diagnostic("repository.lock_identity", self.inner.lock_identity, *args, **kwargs)

    def find_by_identity(self, *args: object, **kwargs: object):
        return _diagnostic("repository.find_by_identity", self.inner.find_by_identity,
                           *args, **kwargs)

    def create_verified(self, *args: object, **kwargs: object):
        return _diagnostic("repository.create_verified", self.inner.create_verified,
                           *args, **kwargs)


class _DiagnosticAudit:
    def __init__(self, inner: AuditService) -> None:
        self.inner = inner

    def append(self, *args: object, **kwargs: object):
        return _diagnostic("audit.append", self.inner.append, *args, **kwargs)


class _FailingAudit:
    def append(self, _transaction: object, _event: AuditEventDraft) -> uuid.UUID:
        raise RuntimeError("synthetic A07 audit failure")


def _archive(private_key: Ed25519PrivateKey, *, version: str, extra: str = "") -> tuple[bytes, bytes]:
    manifest = {
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "synthetic.a07",
        "name": "Synthetic A07",
        "version": version,
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11"],
        "architecture": "x86_64",
        "entry_point": "plugin/main.py",
        "operations": [{"operation_id": "document.render", "output_types": ["DOCX"]}],
        "dependencies": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive_file:
        archive_file.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive_file.writestr("plugin/main.py", "synthetic only")
        if extra:
            archive_file.writestr("plugin/extra.txt", extra)
    payload = buffer.getvalue()
    key_bytes = _KEY_REF.encode("utf-8")
    message = (b"PLM-PLUGIN-PACKAGE\x00v1\x00" + len(key_bytes).to_bytes(2, "big")
               + key_bytes + hashlib.sha256(payload).digest())
    return payload, private_key.sign(message)


def _counts(dsn: str) -> tuple[int, ...]:
    with psycopg.connect(dsn) as conn:
        return tuple(conn.execute(f"SELECT count(*) FROM plm.{table}").fetchone()[0]
                     for table in ("plg_packages", "plg_manifest_operations",
                                   "plg_manifest_dependencies", "plg_package_verifications")) + (
            conn.execute("SELECT count(*) FROM plm.aud_events WHERE action='PLUGIN_PACKAGE_REGISTER'").fetchone()[0],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("A07 integration requires loopback PostgreSQL and numeric run id")

    database = "plg07_" + args.run_id[-10:]
    admin_dsn = _dsn("postgres", args.port)
    runtime = None
    created = False
    result = {"status": "PENDING", "customer_data": False, "external_calls": 0,
              "production_database": False}
    try:
        _create_database(admin_dsn, database)
        created = True
        database_url = _url(database, args.port)
        upgrade_database(database_url, "head")
        runtime = create_database_runtime(database_url)

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        inspector = PluginPackageArchiveInspector(
            PluginManifestParser(),
            PluginPackageSignatureVerifier(_Resolver(public_key)),
        )
        repository = SqlAlchemyPluginPackageRegistrationRepository()
        actor_id = uuid.uuid4()
        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(
                user_id=actor_id, username_display="synthetic-a07",
                username_normalized="synthetic-a07", state="DISABLED",
                deployment_role="NONE",
            ))
            uow.commit()

        def make_service(*, compatible: bool = True, audit: object | None = None):
            return PluginPackageRegistrationService(
                unit_of_work=runtime.unit_of_work,
                inspector=inspector,
                compatibility=_Compatibility(compatible),
                repository=_DiagnosticRepository(repository),
                audit=audit or _DiagnosticAudit(AuditService(SqlAlchemyAuditRepository())),
            )

        trace_id = uuid.uuid4()
        package_bytes, signature = _archive(private_key, version="1.0.0")
        command = RegisterPluginPackageCommand(
            package_bytes, signature, _KEY_REF, "synthetic.win11.v1", trace_id, actor_id,
        )
        owner = make_service()
        first = owner.register(command)
        if first.package_state != "VERIFIED" or first.package_sha256 != hashlib.sha256(package_bytes).digest():
            raise AssertionError("A07 service did not return verified metadata identity")
        expected = (1, 1, 0, 1, 1)
        if _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("Package, operation, verification and Audit did not commit atomically")

        replay = owner.register(command)
        if replay.plugin_package_id != first.plugin_package_id or _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("same package replay was not idempotent")

        different_bytes, different_signature = _archive(
            private_key, version="1.0.0", extra="different synthetic archive",
        )
        try:
            owner.register(RegisterPluginPackageCommand(
                different_bytes, different_signature, _KEY_REF, "synthetic.win11.v1",
                uuid.uuid4(), actor_id,
            ))
        except PluginPackageRegistrationError as exc:
            if exc.code != "PLUGIN_PACKAGE_VERSION_CONFLICT":
                raise
        else:
            raise AssertionError("same version with a different digest was accepted")
        if _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("version conflict wrote package or audit rows")

        rejected_bytes, rejected_signature = _archive(private_key, version="2.0.0")
        try:
            make_service(audit=_FailingAudit()).register(RegisterPluginPackageCommand(
                rejected_bytes, rejected_signature, _KEY_REF, "synthetic.win11.v1",
                uuid.uuid4(), actor_id,
            ))
        except PluginPackageRegistrationError as exc:
            if exc.code != "PLUGIN_PACKAGE_STORE_UNAVAILABLE":
                raise
        else:
            raise AssertionError("Audit failure did not abort package registration")
        if _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("Audit failure left partial package/child/verification rows")

        invalid = RegisterPluginPackageCommand(
            package_bytes, b"\x00" * 64, _KEY_REF, "synthetic.win11.v1",
            uuid.uuid4(), actor_id,
        )
        try:
            owner.register(invalid)
        except PluginPackageRegistrationError as exc:
            if exc.code != "PLUGIN_SIGNATURE_INVALID":
                raise
        else:
            raise AssertionError("invalid signature was accepted")
        try:
            make_service(compatible=False).register(RegisterPluginPackageCommand(
                rejected_bytes, rejected_signature, _KEY_REF, "synthetic.win11.v1",
                uuid.uuid4(), actor_id,
            ))
        except PluginPackageRegistrationError as exc:
            if exc.code != "PLUGIN_OS_INCOMPATIBLE":
                raise
        else:
            raise AssertionError("incompatible package was accepted")
        if _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("rejected package wrote persistent metadata")

        package_id = first.plugin_package_id
        for statement, params in (
            ("UPDATE plm.plg_packages SET plugin_version='9.9.9' WHERE plugin_package_id=%s", (package_id,)),
            ("DELETE FROM plm.plg_manifest_operations WHERE plugin_package_id=%s", (package_id,)),
            ("TRUNCATE plm.plg_package_verifications", ()),
        ):
            with psycopg.connect(_dsn(database, args.port)) as conn:
                try:
                    with conn.transaction():
                        conn.execute(statement, params)
                except psycopg.Error:
                    pass
                else:
                    raise AssertionError("A07 allowed mutation or TRUNCATE of package history")
        if _counts(_dsn(database, args.port)) != expected:
            raise AssertionError("append-only guards changed registered history")

        result.update(
            status="PASS_LIMITED",
            postgresql="18.x hosted temporary database",
            package_operation_verification_audit_rows=expected,
            same_digest_idempotent=True,
            same_version_digest_conflict=True,
            audit_failure_rolled_back=True,
            invalid_signature_wrote_nothing=True,
            incompatible_package_wrote_nothing=True,
            append_only_and_truncate_guards=True,
            customer_data=False,
            external_calls=0,
            production_database=False,
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            _drop_database(admin_dsn, database)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
