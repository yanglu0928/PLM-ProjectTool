from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from plm_assistant.modules.plugin.application.package_archive_inspector import (
    PluginPackageArchiveInspector,
)
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageCompatibilityAssessment,
    PluginPackageIdentity,
    PluginPackageRegistrationError,
    PluginPackageRegistrationService,
    RegisterPluginPackageCommand,
)
from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    TrustedPluginSigner,
)


class _SignerResolver:
    def __init__(self, key_ref: str, key: bytes) -> None:
        self.key_ref, self.key = key_ref, key

    def resolve_trusted_signer(self, signer_key_ref: str):
        if signer_key_ref != self.key_ref:
            return None
        return TrustedPluginSigner(self.key_ref, self.key)


class _Compatibility:
    def __init__(self, compatible: bool = True, failure_code: str | None = None) -> None:
        self.compatible, self.failure_code = compatible, failure_code
        self.calls = 0

    def evaluate(self, _manifest, *, policy_ref: str):
        self.calls += 1
        if policy_ref != "host.win11.v1":
            return PluginPackageCompatibilityAssessment(False, "PLUGIN_OS_INCOMPATIBLE")
        return PluginPackageCompatibilityAssessment(self.compatible, self.failure_code)


class _Repository:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], PluginPackageIdentity] = {}
        self.calls: list[str] = []

    def lock_identity(self, _tx, *, plugin_id: str, version: str) -> None:
        self.calls.append("lock")

    def find_by_identity(self, _tx, *, plugin_id: str, version: str):
        self.calls.append("find")
        return self.records.get((plugin_id, version))

    def create_verified(
        self, _tx, *, package_id, manifest, manifest_snapshot,
        signature_verification, signature, compatibility_policy_ref,
        evidence_fingerprint, verified_at,
    ):
        del evidence_fingerprint, verified_at
        self.calls.append("create")
        identity = PluginPackageIdentity(
            package_id, manifest.plugin_id, manifest.version,
            signature_verification.package_sha256, signature,
            signature_verification.signer_key_ref, compatibility_policy_ref,
            copy.deepcopy(manifest_snapshot), "VERIFIED",
        )
        self.records[(manifest.plugin_id, manifest.version)] = identity
        return identity


class _Audit:
    def __init__(self, fail: bool = False) -> None:
        self.events = []
        self.fail = fail

    def append(self, _tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)
        return uuid.uuid4()


class _UnitOfWork:
    def __init__(self, repository: _Repository, audit: _Audit) -> None:
        self.repository, self.audit = repository, audit
        self.committed = False

    def __enter__(self):
        self.records_before = copy.deepcopy(self.repository.records)
        self.events_before = list(self.audit.events)
        return self

    def commit(self):
        self.committed = True

    def __exit__(self, exc_type, _exc_value, _traceback):
        if exc_type is not None or not self.committed:
            self.repository.records = self.records_before
            self.audit.events[:] = self.events_before
        return False


def _archive(private_key: Ed25519PrivateKey, key_ref: str, *, extra: str = ""):
    manifest = {
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "synthetic.echo",
        "name": "Synthetic Echo",
        "version": "1.0.0",
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11"],
        "architecture": "x86_64",
        "entry_point": "plugin/main.py",
        "operations": [{
            "operation_id": "document.render",
            "output_types": ["DOCX"],
        }],
        "dependencies": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("plugin/main.py", "synthetic only")
        if extra:
            archive.writestr("plugin/extra.txt", extra)
    payload = buffer.getvalue()
    key_bytes = key_ref.encode("utf-8")
    signed = (
        b"PLM-PLUGIN-PACKAGE\x00v1\x00"
        + len(key_bytes).to_bytes(2, "big")
        + key_bytes
        + hashlib.sha256(payload).digest()
    )
    return payload, private_key.sign(signed)


class PluginPackageRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.key_ref = "synthetic-key-v1"
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.archive, self.signature = _archive(self.private, self.key_ref)
        resolver = _SignerResolver(self.key_ref, public)
        inspector = PluginPackageArchiveInspector(
            PluginManifestParser(), PluginPackageSignatureVerifier(resolver))
        self.repository, self.audit = _Repository(), _Audit()
        self.compatibility = _Compatibility()
        self.service = PluginPackageRegistrationService(
            unit_of_work=lambda: _UnitOfWork(self.repository, self.audit),
            inspector=inspector,
            compatibility=self.compatibility,
            repository=self.repository,
            audit=self.audit,
            clock=lambda: datetime(2026, 11, 3, tzinfo=timezone.utc),
        )
        self.command = RegisterPluginPackageCommand(
            self.archive, self.signature, self.key_ref, "host.win11.v1",
            uuid.uuid4(), uuid.uuid4(),
        )

    def test_registers_verified_metadata_without_persisting_archive_bytes(self):
        result = self.service.register(self.command)
        self.assertEqual(result.package_state, "VERIFIED")
        self.assertEqual(result.plugin_id_normalized, "synthetic.echo")
        self.assertEqual(result.package_sha256, hashlib.sha256(self.archive).digest())
        self.assertNotIn(self.archive, repr(result).encode("utf-8"))
        self.assertEqual(self.repository.calls, ["lock", "find", "create"])
        self.assertEqual(len(self.audit.events), 1)
        self.assertEqual(self.audit.events[0].action, "PLUGIN_PACKAGE_REGISTER")
        self.assertEqual(self.audit.events[0].target_object_type, "PLG-01")
        self.assertEqual(self.audit.events[0].after_state, "VERIFIED")
        self.assertEqual(self.compatibility.calls, 1)

    def test_same_plugin_version_and_digest_is_idempotent(self):
        first = self.service.register(self.command)
        second = self.service.register(self.command)
        self.assertEqual(first.plugin_package_id, second.plugin_package_id)
        self.assertEqual(self.repository.calls.count("create"), 1)
        self.assertEqual(len(self.audit.events), 1)

    def test_same_plugin_version_with_different_digest_is_rejected(self):
        changed, signature = _archive(self.private, self.key_ref, extra="other archive bytes")
        command = RegisterPluginPackageCommand(
            changed, signature, self.key_ref, "host.win11.v1",
            self.command.trace_id, self.command.actor_id,
        )
        self.service.register(self.command)
        with self.assertRaisesRegex(
            PluginPackageRegistrationError, "PLUGIN_PACKAGE_VERSION_CONFLICT"
        ):
            self.service.register(command)
        self.assertEqual(len(self.repository.records), 1)
        self.assertEqual(len(self.audit.events), 1)

    def test_invalid_signature_writes_nothing(self):
        invalid = RegisterPluginPackageCommand(
            self.archive, b"\x00" * 64, self.key_ref, "host.win11.v1",
            self.command.trace_id, self.command.actor_id,
        )
        with self.assertRaisesRegex(
            PluginPackageRegistrationError, "PLUGIN_SIGNATURE_INVALID"
        ):
            self.service.register(invalid)
        self.assertEqual(self.repository.records, {})
        self.assertEqual(self.repository.calls, [])
        self.assertEqual(self.audit.events, [])

    def test_incompatible_package_writes_nothing(self):
        self.compatibility.compatible = False
        self.compatibility.failure_code = "PLUGIN_OS_INCOMPATIBLE"
        with self.assertRaisesRegex(
            PluginPackageRegistrationError, "PLUGIN_OS_INCOMPATIBLE"
        ):
            self.service.register(self.command)
        self.assertEqual(self.repository.records, {})
        self.assertEqual(self.repository.calls, [])
        self.assertEqual(self.audit.events, [])

    def test_audit_failure_rolls_back_package_metadata(self):
        self.audit.fail = True
        with self.assertRaisesRegex(
            PluginPackageRegistrationError, "PLUGIN_PACKAGE_STORE_UNAVAILABLE"
        ):
            self.service.register(self.command)
        self.assertEqual(self.repository.records, {})
        self.assertEqual(self.audit.events, [])

    def test_command_repr_does_not_disclose_archive_or_signature(self):
        rendered = repr(self.command)
        self.assertNotIn(self.archive.hex(), rendered)
        self.assertNotIn(self.signature.hex(), rendered)


if __name__ == "__main__":
    unittest.main()
