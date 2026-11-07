from __future__ import annotations

import base64
import hashlib
import io
import json
import stat
import unittest
import zipfile
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.plugin.application.manifest_parser import (
    PluginManifestError,
    PluginManifestParser,
)
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    MAX_ARCHIVE_ITEMS,
    MAX_CENTRAL_DIRECTORY_BYTES,
    MAX_COMPRESSION_RATIO,
    MAX_MANIFEST_BYTES,
    MAX_PACKAGE_BYTES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    InspectedPluginPackage,
    PluginPackageArchiveInspector,
    PluginPackageInspectionError,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerifier,
    PluginSignatureVerificationError,
    TrustedPluginSigner,
    _signature_message,
)
from plm_assistant.modules.plugin.infrastructure.packaged_signer_resolver import (
    PackagedPluginSignerResolver,
    _load_packaged_manifest,
)


_KEY_REF = "synthetic:archive-publisher-v1"


def _manifest(entry_point: str = "plugin/main.py") -> bytes:
    return json.dumps({
        "schema_version": "plm.plugin.manifest.v1",
        "plugin_id": "demo.echo",
        "name": "Demo Echo",
        "version": "1.0.0",
        "plugin_api_version": "1.0.0",
        "supported_os": ["windows-11", "windows-server-2025"],
        "architecture": "x86_64",
        "entry_point": entry_point,
        "operations": [{"operation_id": "demo.echo", "output_types": ["text/plain"]}],
        "dependencies": [],
    }, separators=(",", ":")).encode("utf-8")


def _archive(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


class _StaticResolver:
    def __init__(self, signer: TrustedPluginSigner | None) -> None:
        self.signer = signer

    def resolve_trusted_signer(self, signer_key_ref: str) -> TrustedPluginSigner | None:
        if self.signer is not None and self.signer.signer_key_ref == signer_key_ref:
            return self.signer
        return None


class PluginPackageArchiveInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.signer = TrustedPluginSigner(_KEY_REF, self.public)
        self.package = _archive([
            ("manifest.json", _manifest()),
            ("plugin/main.py", b"def run(): return 'synthetic'\n"),
        ])
        digest = hashlib.sha256(self.package).digest()
        self.signature = self.private.sign(_signature_message(_KEY_REF, digest))
        self.inspector = PluginPackageArchiveInspector(
            PluginManifestParser(),
            PluginPackageSignatureVerifier(_StaticResolver(self.signer)),
        )

    def reject_archive(self, candidate: bytes) -> None:
        with self.assertRaises(PluginPackageInspectionError):
            self.inspector.inspect_and_verify(
                candidate,
                detached_signature=self.signature,
                signer_key_ref=_KEY_REF,
            )

    def test_valid_root_manifest_entry_point_and_exact_archive_signature(self) -> None:
        result = self.inspector.inspect_and_verify(
            self.package,
            detached_signature=self.signature,
            signer_key_ref=_KEY_REF,
        )
        self.assertIsInstance(result, InspectedPluginPackage)
        self.assertEqual(result.manifest.entry_point, "plugin/main.py")
        self.assertEqual(
            result.signature_verification.package_sha256,
            hashlib.sha256(self.package).digest(),
        )
        self.assertEqual(result.archive_item_count, 2)

    def test_archive_or_manifest_tampering_cannot_be_mixed(self) -> None:
        changed = _archive([
            ("manifest.json", _manifest("plugin/other.py")),
            ("plugin/main.py", b"synthetic"),
            ("plugin/other.py", b"entry"),
        ])
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            self.inspector.inspect_and_verify(
                changed,
                detached_signature=self.signature,
                signer_key_ref=_KEY_REF,
            )
        self.assertEqual(caught.exception.code, "PLUGIN_SIGNATURE_INVALID")

        mismatch = _archive([
            ("manifest.json", _manifest("plugin/missing.py")),
            ("plugin/main.py", b"synthetic"),
        ])
        self.reject_archive(mismatch)

    def test_missing_duplicate_case_conflicting_and_nonroot_manifest_rejected(self) -> None:
        self.reject_archive(_archive([("plugin/main.py", b"x")]))
        self.reject_archive(_archive([
            ("manifest.json", _manifest()),
            ("manifest.json", _manifest()),
            ("plugin/main.py", b"x"),
        ]))
        self.reject_archive(_archive([
            ("manifest.json", _manifest()),
            ("MANIFEST.JSON", _manifest()),
            ("plugin/main.py", b"x"),
        ]))
        self.reject_archive(_archive([
            ("nested/manifest.json", _manifest()),
            ("plugin/main.py", b"x"),
        ]))

    def test_traversal_windows_alias_links_devices_and_encryption_rejected(self) -> None:
        backslash = chr(92)
        for name in (
            "../escape.py",
            "plugin/../../escape.py",
            "/absolute.py",
            "C:/drive.py",
            "folder" + backslash + "escape.py",
            "plugin/CON.txt",
            "plugin/CON .txt",
            "plugin/trailing.",
            "plugin/trailing ",
        ):
            with self.subTest(name=name):
                entries = [
                    ("manifest.json", _manifest("plugin/main.py")),
                    (name, b"x"),
                    ("plugin/main.py", b"entry"),
                ]
                candidate = bytearray(_archive(entries))
                if backslash in name:
                    normalized_name = name.replace(backslash, "/").encode("utf-8")
                    self.assertIn(normalized_name, candidate)
                    candidate = candidate.replace(normalized_name, name.encode("utf-8"))
                self.reject_archive(bytes(candidate))

        symlink = zipfile.ZipInfo("plugin/link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("manifest.json", _manifest("plugin/link"))
            archive.writestr(symlink, "plugin/main.py")
        self.reject_archive(stream.getvalue())

        encrypted = bytearray(self.package)
        local_header = encrypted.find(b"PK\x03\x04")
        central_header = encrypted.find(b"PK\x01\x02")
        self.assertGreaterEqual(local_header, 0)
        self.assertGreaterEqual(central_header, 0)
        encrypted[local_header + 6] |= 0x01
        encrypted[central_header + 8] |= 0x01
        self.reject_archive(bytes(encrypted))

    def test_eocd_preflight_bounds_directory_and_rejects_zip64_multidisk_and_prefix(self) -> None:
        valid = bytearray(self.package)
        eocd = valid.rfind(b"PK\x05\x06")
        self.assertGreaterEqual(eocd, 0)

        too_many = bytearray(valid)
        too_many[eocd + 10:eocd + 12] = (MAX_ARCHIVE_ITEMS + 1).to_bytes(2, "little")
        self.reject_archive(bytes(too_many))

        zip64 = bytearray(valid)
        zip64[eocd + 10:eocd + 12] = (0xFFFF).to_bytes(2, "little")
        self.reject_archive(bytes(zip64))

        multidisk = bytearray(valid)
        multidisk[eocd + 4:eocd + 6] = (1).to_bytes(2, "little")
        self.reject_archive(bytes(multidisk))

        bad_comment_length = bytearray(valid)
        bad_comment_length[eocd + 20:eocd + 22] = (1).to_bytes(2, "little")
        self.reject_archive(bytes(bad_comment_length))

        self.reject_archive(b"stub" + bytes(valid))

        with patch(
            "plm_assistant.modules.plugin.application.package_archive_inspector.MAX_CENTRAL_DIRECTORY_BYTES",
            1,
        ):
            self.reject_archive(bytes(valid))

    def test_member_count_size_ratio_and_package_bounds_fail_closed(self) -> None:
        small = _archive([("manifest.json", _manifest()), ("plugin/main.py", b"x")])
        with patch(
            "plm_assistant.modules.plugin.application.package_archive_inspector.MAX_PACKAGE_BYTES",
            len(small) - 1,
        ):
            self.reject_archive(small)

        with patch(
            "plm_assistant.modules.plugin.application.package_archive_inspector.MAX_ARCHIVE_ITEMS",
            1,
        ):
            self.reject_archive(small)

        with patch(
            "plm_assistant.modules.plugin.application.package_archive_inspector.MAX_TOTAL_UNCOMPRESSED_BYTES",
            10,
        ):
            self.reject_archive(small)

        bomb = _archive([
            ("manifest.json", _manifest()),
            ("plugin/main.py", b"a" * (MAX_COMPRESSION_RATIO * 1000)),
        ])
        self.reject_archive(bomb)

        with patch(
            "plm_assistant.modules.plugin.application.package_archive_inspector.MAX_MANIFEST_BYTES",
            20,
        ):
            self.reject_archive(small)

    def test_bad_zip_manifest_schema_and_empty_packaged_trust_are_rejected(self) -> None:
        self.reject_archive(b"not a zip")
        bad_manifest = _archive([
            ("manifest.json", b'{"schema_version":"wrong"}'),
            ("plugin/main.py", b"x"),
        ])
        with self.assertRaises(PluginManifestError):
            self.inspector.inspect_and_verify(
                bad_manifest,
                detached_signature=self.signature,
                signer_key_ref=_KEY_REF,
            )

        empty = _load_packaged_manifest()
        self.assertIn(b'"keys":[]', empty)
        inspector = PluginPackageArchiveInspector(
            PluginManifestParser(),
            PluginPackageSignatureVerifier(PackagedPluginSignerResolver()),
        )
        with self.assertRaises(PluginSignatureVerificationError) as caught:
            inspector.inspect_and_verify(
                self.package,
                detached_signature=self.signature,
                signer_key_ref=_KEY_REF,
            )
        self.assertEqual(caught.exception.code, "PLUGIN_SIGNER_UNTRUSTED")


if __name__ == "__main__":
    unittest.main()
