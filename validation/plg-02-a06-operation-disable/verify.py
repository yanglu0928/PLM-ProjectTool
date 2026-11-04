"""PostgreSQL 18 integration for the controlled Plugin operation-disable owner."""
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
from sqlalchemy import URL
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.plugin.application.activation_owner import (
    DisablePluginInstallationCommand,
    EnablePluginOperationsCommand,
    PluginActivationOwner,
    PluginActivationOwnerError,
)
from plm_assistant.modules.plugin.application.installation_metadata import (
    PluginInstallationMetadataQuery,
    PluginInstallationMetadataService,
)
from plm_assistant.modules.plugin.infrastructure.installation_metadata_repository import (
    SqlAlchemyPluginInstallationMetadataRepository,
)
from plm_assistant.modules.plugin.application.installation_owner import (
    PluginInstallationEvidence,
    PluginInstallationOwner,
    RecordPluginInstallationCommand,
)
from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
from plm_assistant.modules.plugin.application.package_archive_inspector import PluginPackageArchiveInspector
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageCompatibilityAssessment,
    PluginPackageRegistrationService,
    RegisterPluginPackageCommand,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    TrustedPluginSigner,
)
from plm_assistant.modules.plugin.infrastructure.activation_owner_repository import (
    SqlAlchemyPluginActivationRepository,
)
from plm_assistant.modules.plugin.infrastructure.installation_owner_repository import (
    SqlAlchemyPluginInstallationRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.plugin.application.installation_disable import (
    PluginInstallationDisableError, PluginInstallationDisableService,
)
from plm_assistant.modules.plugin.infrastructure.installation_disable_result_repository import (
    SqlAlchemyPluginDisableResultRepository,
)
from plm_assistant.modules.plugin.infrastructure.package_registration_repository import (
    SqlAlchemyPluginPackageRegistrationRepository,
)

_KEY_REF = "synthetic-a06-disable-key"
_RUNTIME = {
    "schema_version": "1",
    "os": "windows-11",
    "architecture": "x86_64",
    "python_version": "3.13.17",
    "dependency_versions": {},
}


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
    def evaluate(self, _manifest: object, *, policy_ref: str):
        if policy_ref != "synthetic.win11.v1":
            return PluginPackageCompatibilityAssessment(False, "PLUGIN_OS_INCOMPATIBLE")
        return PluginPackageCompatibilityAssessment(True)


class _InstalledEvidence:
    def inspect_installed_package(self, package: object):
        return PluginInstallationEvidence(
            package.plugin_package_id, package.package_sha256, True, True, dict(_RUNTIME),
        )


class _ReadAccess:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id
    def authorized_admin(self, _transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: object):
        if (type(session_token) is not bytes or len(session_token) != 32
                or type(csrf_token) is not bytes or len(csrf_token) != 32):
            return None
        return self.actor_id


class _ReadLicense:
    def require_valid(self, *, trace_id: uuid.UUID) -> None:
        if type(trace_id) is not uuid.UUID or trace_id.int == 0:
            raise RuntimeError("synthetic A06 License denied")


class _FailingAudit:
    def append(self, _transaction: object, _event: object) -> uuid.UUID:
        raise RuntimeError("synthetic A06 audit failure")


def _signed_package(private_key: Ed25519PrivateKey) -> tuple[bytes, bytes]:
    manifest = {
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "synthetic.a06",
        "name": "合成插件A06",
        "version": "1.0.0",
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11"],
        "architecture": "x86_64",
        "entry_point": "plugin/main.py",
        "operations": [
            {"operation_id": "document.render", "output_types": ["DOCX"]},
            {"operation_id": "document.export", "output_types": ["XLSX"]},
        ],
        "dependencies": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("plugin/main.py", "synthetic inert fixture")
    payload = buffer.getvalue()
    key_bytes = _KEY_REF.encode("utf-8")
    signed = (b"PLM-PLUGIN-PACKAGE\x00v1\x00" + len(key_bytes).to_bytes(2, "big")
              + key_bytes + hashlib.sha256(payload).digest())
    return payload, private_key.sign(signed)


def _state(dsn: str, installation_id: uuid.UUID) -> tuple[str, int, int, int]:
    with psycopg.connect(dsn) as conn:
        state, version = conn.execute(
            "SELECT installation_state,lock_version FROM plm.plg_installations "
            "WHERE plugin_installation_id=%s", (installation_id,),
        ).fetchone()
        operations = conn.execute(
            "SELECT count(*) FROM plm.plg_enabled_operations "
            "WHERE plugin_installation_id=%s", (installation_id,),
        ).fetchone()[0]
        history = conn.execute(
            "SELECT count(*) FROM plm.plg_enabled_operation_history "
            "WHERE plugin_installation_id=%s", (installation_id,),
        ).fetchone()[0]
        return state, version, operations, history


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch(r"[0-9]{1,12}", args.run_id):
        raise ValueError("A06 integration requires loopback PostgreSQL and numeric run id")

    database = "plg06_" + args.run_id[-10:]
    admin_dsn = _dsn("postgres", args.port)
    runtime = None
    created = False
    result = {
        "status": "PENDING",
        "postgresql": "18.x hosted temporary database",
        "customer_data": False,
        "external_calls": 0,
        "production_database": False,
    }
    try:
        _create_database(admin_dsn, database)
        created = True
        database_url = _url(database, args.port)
        upgrade_database(database_url, "head")
        runtime = create_database_runtime(database_url)
        audit = AuditService(SqlAlchemyAuditRepository())

        actor_id = uuid.uuid4()
        with runtime.unit_of_work() as uow:
            uow.session.add(UserRow(
                user_id=actor_id, username_display="synthetic-a06",
                username_normalized="synthetic-a06", state="DISABLED",
                deployment_role="NONE",
            ))
            uow.commit()

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        payload, signature = _signed_package(private_key)
        registration = PluginPackageRegistrationService(
            unit_of_work=runtime.unit_of_work,
            inspector=PluginPackageArchiveInspector(
                PluginManifestParser(),
                PluginPackageSignatureVerifier(_Resolver(public_key)),
            ),
            compatibility=_Compatibility(),
            repository=SqlAlchemyPluginPackageRegistrationRepository(),
            audit=audit,
        )
        trace_id = uuid.uuid4()
        package = registration.register(RegisterPluginPackageCommand(
            payload, signature, _KEY_REF, "synthetic.win11.v1", trace_id, actor_id,
        ))
        installation_id = uuid.uuid4()
        installer = PluginInstallationOwner(
            unit_of_work=runtime.unit_of_work,
            evidence=_InstalledEvidence(),
            repository=SqlAlchemyPluginInstallationRepository(),
            audit=audit,
        )
        installation = installer.record(RecordPluginInstallationCommand(
            installation_id, package.plugin_package_id, actor_id, uuid.uuid4(),
        ))
        if installation.installation_state != "INSTALLED":
            raise AssertionError("synthetic Installation fact did not start INSTALLED")

        activation_repo = SqlAlchemyPluginActivationRepository()
        activation = PluginActivationOwner(
            unit_of_work=runtime.unit_of_work, repository=activation_repo, audit=audit,
        )
        enabled = activation.enable(EnablePluginOperationsCommand(
            installation_id, ("document.render", "document.export"), 0,
            actor_id, uuid.uuid4(),
        ))
        if enabled.installation_state != "ENABLED" or len(enabled.enabled_operations) != 2:
            raise AssertionError("activation setup did not enable the expected operation set")
        if _state(_dsn(database, args.port), installation_id) != ("ENABLED", 1, 2, 2):
            raise AssertionError("enabled state was not persisted atomically")

        metadata = PluginInstallationMetadataService(
            unit_of_work=runtime.unit_of_work,
            access=_ReadAccess(actor_id),
            license_guard=_ReadLicense(),
            repository=SqlAlchemyPluginInstallationMetadataRepository(),
        )
        detail = metadata.get(
            PluginInstallationMetadataQuery(b"m" * 32, uuid.uuid4()),
            installation_id,
        )
        if (detail.installation_state != "ENABLED"
                or detail.lock_version != 1
                or detail.etag != '"v1"'
                or detail.enabled_operations != ("document.export", "document.render")
                or len(detail.operations) != 2
                or detail.package_sha256 != package.package_sha256.hex()
                or "signature" in detail.runtime_snapshot):
            raise AssertionError("Installation detail projection or ETag was invalid")

        stale = DisablePluginInstallationCommand(
            installation_id, 0, actor_id, uuid.uuid4(),
        )
        try:
            activation.disable(stale)
        except PluginActivationOwnerError as exc:
            if exc.code != "PLUGIN_LOCK_VERSION_CONFLICT":
                raise
        else:
            raise AssertionError("stale disable lock version was accepted")
        if _state(_dsn(database, args.port), installation_id) != ("ENABLED", 1, 2, 2):
            raise AssertionError("stale disable changed persistent facts")

        failing = PluginActivationOwner(
            unit_of_work=runtime.unit_of_work,
            repository=activation_repo,
            audit=_FailingAudit(),
        )
        try:
            failing.disable(DisablePluginInstallationCommand(
                installation_id, 1, actor_id, uuid.uuid4(),
            ))
        except PluginActivationOwnerError as exc:
            if exc.code != "PLUGIN_ACTIVATION_STORE_UNAVAILABLE":
                raise
        else:
            raise AssertionError("synthetic Audit failure did not reject disable")
        if _state(_dsn(database, args.port), installation_id) != ("ENABLED", 1, 2, 2):
            raise AssertionError("Audit failure left partial disable facts")

        disabled = activation.disable(DisablePluginInstallationCommand(
            installation_id, 1, actor_id, uuid.uuid4(),
        ))
        if (disabled.installation_state != "DISABLED" or disabled.enabled_operations
                or not disabled.changed
                or _state(_dsn(database, args.port), installation_id) != ("DISABLED", 2, 0, 4)):
            raise AssertionError("multi-operation disable did not commit atomically")

        replay = activation.disable(DisablePluginInstallationCommand(
            installation_id, 2, actor_id, uuid.uuid4(),
        ))
        if replay.changed or _state(_dsn(database, args.port), installation_id) != ("DISABLED", 2, 0, 4):
            raise AssertionError("exact disabled replay changed persistent facts")

        with psycopg.connect(_dsn(database, args.port)) as conn:
            disable_audits = conn.execute(
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='PLUGIN_OPERATION_DISABLE' AND target_object_id=%s",
                (installation_id,),
            ).fetchone()[0]
        if disable_audits != 2:
            raise AssertionError("per-operation disable Audit events are incomplete")

        api_installation_id = uuid.uuid4()
        api_recorded = installer.record(RecordPluginInstallationCommand(
            api_installation_id, package.plugin_package_id, actor_id, uuid.uuid4(),
        ))
        if api_recorded.installation_state != "INSTALLED":
            raise AssertionError("A08 synthetic Installation did not start installed")
        api_enabled = activation.enable(EnablePluginOperationsCommand(
            api_installation_id, ("document.render", "document.export"), 0,
            actor_id, uuid.uuid4(),
        ))
        if api_enabled.installation_state != "ENABLED":
            raise AssertionError("A08 synthetic Installation did not enable")
        disable_service = PluginInstallationDisableService(
            unit_of_work=runtime.unit_of_work,
            access=_ReadAccess(actor_id),
            owner=activation,
            receipts=SqlAlchemyIdempotencyReceipts(),
            results=SqlAlchemyPluginDisableResultRepository(),
            license_guard=_ReadLicense(),
        )
        request_key = "a08-plugin-disable-stable-key"
        disable_command = DisablePluginInstallationCommand(
            api_installation_id, 1, actor_id, uuid.uuid4(),
        )
        first_response = disable_service.disable(
            disable_command, session_token=b"m" * 32, csrf_token=b"c" * 32,
            idempotency_key=request_key,
        )
        replay_response = disable_service.disable(
            DisablePluginInstallationCommand(
                api_installation_id, 1, actor_id, uuid.uuid4(),
            ),
            session_token=b"m" * 32, csrf_token=b"c" * 32,
            idempotency_key=request_key,
        )
        if (first_response != replay_response
                or not first_response.changed
                or first_response.result_lock_version != 2
                or _state(_dsn(database, args.port), api_installation_id)
                != ("DISABLED", 2, 0, 4)):
            raise AssertionError("A08 exact idempotent disable replay was not immutable")
        try:
            disable_service.disable(
                DisablePluginInstallationCommand(
                    api_installation_id, 2, actor_id, uuid.uuid4(),
                ),
                session_token=b"m" * 32, csrf_token=b"c" * 32,
                idempotency_key=request_key,
            )
        except PluginInstallationDisableError as exc:
            if exc.code != "CONFLICT_IDEMPOTENCY":
                raise
        else:
            raise AssertionError("A08 same key with a different payload was accepted")
        with psycopg.connect(_dsn(database, args.port)) as conn:
            result_rows = conn.execute(
                "SELECT count(*) FROM plm.plg_disable_results "
                "WHERE plugin_installation_id=%s", (api_installation_id,),
            ).fetchone()[0]
            receipt_rows = conn.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts "
                "WHERE actor_id=%s AND operation='V1_PLUGIN_DISABLE' "
                "AND state='COMPLETED'", (actor_id,),
            ).fetchone()[0]
            api_disable_audits = conn.execute(
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='PLUGIN_OPERATION_DISABLE' AND target_object_id=%s",
                (api_installation_id,),
            ).fetchone()[0]
        if result_rows != 1 or receipt_rows != 1 or api_disable_audits != 2:
            raise AssertionError("A08 result/receipt/audit transaction was not atomic")
        with psycopg.connect(_dsn(database, args.port)) as conn:
            try:
                conn.execute(
                    "UPDATE plm.plg_disable_results SET changed=false "
                    "WHERE plugin_installation_id=%s", (api_installation_id,),
                )
            except psycopg.Error:
                conn.rollback()
            else:
                raise AssertionError("A08 immutable result row accepted direct UPDATE")
        result["plugin_installation_disable_api_validation"] = {
            "status": "PASS_LIMITED",
            "changed": first_response.changed,
            "result_lock_version": first_response.result_lock_version,
            "idempotent_replay_exact": first_response == replay_response,
            "different_payload_conflict": True,
            "immutable_result_rows": result_rows,
            "completed_receipts": receipt_rows,
            "operation_audit_rows": api_disable_audits,
            "customer_data": False,
            "external_calls": 0,
            "production_database": False,
        }

        result.update(
            status="PASS_LIMITED",
            installation_state="DISABLED",
            lock_version=2,
            active_operations=0,
            immutable_history_rows=4,
            disable_audit_rows=2,
            stale_lock_rejected=True,
            audit_failure_rolled_back=True,
            exact_replay_noop=True,
            customer_data=False,
            external_calls=0,
            production_database=False,
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        if created:
            _drop_database(admin_dsn, database)

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
