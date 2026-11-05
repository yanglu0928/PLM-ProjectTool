from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.plugin.application.installation_owner import InstallablePluginPackage
from plm_assistant.modules.plugin.application.manifest_parser import PluginManifestParser
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    PluginPackageArchiveInspector,
)
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageRegistrationService,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    TrustedPluginSigner,
    _signature_message,
)
from plm_assistant.modules.plugin.infrastructure.local_installation_materializer import (
    LocalPluginInstallationMaterializer,
    PluginInstallationMaterializationError,
)

_KEY_REF = "synthetic:installation-materializer-v1"
_RUNTIME = {
    "schema_version": "1",
    "os": "windows-11",
    "architecture": "x86_64",
    "python_version": "3.13.17",
    "dependency_versions": {},
}


def _manifest() -> bytes:
    return json.dumps({
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "demo.echo",
        "name": "Demo Echo",
        "version": "1.0.0",
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11", "windows-server-2025"],
        "architecture": "x86_64",
        "entry_point": "plugin/main.py",
        "operations": [{"operation_id": "demo.echo", "output_types": ["text/plain"]}],
        "dependencies": [],
    }, separators=(",", ":")).encode("utf-8")


def _archive(entries: list[tuple[str, bytes]]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


class _Resolver:
    def __init__(self, signer: TrustedPluginSigner) -> None:
        self.signer = signer

    def resolve_trusted_signer(self, signer_key_ref: str):
        return self.signer if signer_key_ref == self.signer.signer_key_ref else None


class PluginInstallationMaterializerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = LocalFileStorage(self.root)
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        self.parser = PluginManifestParser()
        self.inspector = PluginPackageArchiveInspector(
            self.parser,
            PluginPackageSignatureVerifier(
                _Resolver(TrustedPluginSigner(_KEY_REF, public)),
            ),
        )
        self.installation_id = uuid.uuid4()
        self.package_id = uuid.uuid4()
        self.contents = b"def run(): return 'fixture'\n"
        self.archive_bytes = _archive([
            ("manifest.json", _manifest()),
            ("plugin/main.py", self.contents),
            ("plugin/data/info.txt", b"synthetic data"),
        ])
        self.package = self._register_package(self.archive_bytes)
        self.materializer = LocalPluginInstallationMaterializer(
            storage=self.storage,
            inspector=self.inspector,
            runtime_snapshot_provider=lambda: dict(_RUNTIME),
        )

    def _register_package(self, archive_bytes: bytes) -> InstallablePluginPackage:
        digest = hashlib.sha256(archive_bytes).digest()
        signature = self.private.sign(_signature_message(_KEY_REF, digest))
        self.storage.store_plugin_package_archive(
            package_id=self.package_id,
            archive_bytes=archive_bytes,
            expected_sha256=digest,
            expected_size=len(archive_bytes),
        )
        manifest = self.parser.parse(_manifest())
        return InstallablePluginPackage(
            self.package_id, manifest.plugin_id, digest,
            PluginPackageRegistrationService._manifest_snapshot(manifest),
            manifest.version, signature, _KEY_REF, "synthetic.win11.v1", "VERIFIED",
        )

    def test_materializes_exact_signed_members_and_replays_without_overwrite(self) -> None:
        target = self.materializer.materialize(
            self.package, installation_id=self.installation_id,
        )
        self.assertEqual(
            (target / "plugin" / "main.py").read_bytes(), self.contents,
        )
        self.assertEqual(
            (target / "plugin" / "data" / "info.txt").read_bytes(), b"synthetic data",
        )
        self.assertEqual(
            self.materializer.materialize(
                self.package, installation_id=self.installation_id,
            ),
            target,
        )
        evidence = self.materializer.inspect_installed_package(
            self.package, installation_id=self.installation_id,
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.plugin_installation_id, self.installation_id)
        self.assertTrue(evidence.installation_present)
        self.assertTrue(evidence.compatible)

    def test_unknown_or_modified_target_and_wrong_id_fail_closed(self) -> None:
        target = self.materializer.materialize(
            self.package, installation_id=self.installation_id,
        )
        (target / "unrelated.txt").write_bytes(b"must remain")
        self.assertIsNone(self.materializer.inspect_installed_package(
            self.package, installation_id=self.installation_id,
        ))
        with self.assertRaises(PluginInstallationMaterializationError):
            self.materializer.materialize(
                self.package, installation_id=self.installation_id,
            )
        self.assertEqual((target / "unrelated.txt").read_bytes(), b"must remain")
        self.assertIsNone(self.materializer.inspect_installed_package(
            self.package, installation_id=uuid.uuid4(),
        ))

    def test_signed_zip_slip_archive_is_rejected_before_materialization(self) -> None:
        malicious = _archive([
            ("manifest.json", _manifest()),
            ("plugin/main.py", self.contents),
            ("../outside.txt", b"escape"),
        ])
        package = self._register_package(malicious)
        with self.assertRaises(PluginInstallationMaterializationError):
            self.materializer.materialize(
                package, installation_id=uuid.uuid4(),
            )
        self.assertFalse((self.root.parent / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
