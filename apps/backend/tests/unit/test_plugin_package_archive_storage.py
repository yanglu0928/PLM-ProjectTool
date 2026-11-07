from __future__ import annotations

import hashlib
import tempfile
import uuid
import unittest
from pathlib import Path

from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError,
)


class LocalPluginPackageArchiveStorageTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        root = Path(self._temporary.name) / "data"
        root.mkdir()
        self.storage = LocalFileStorage(root)

    def tearDown(self):
        self._temporary.cleanup()

    def test_publish_and_exact_replay_are_digest_bound(self):
        package_id = uuid.uuid4()
        body = b"signed synthetic plugin archive"
        digest = hashlib.sha256(body).digest()
        first = self.storage.store_plugin_package_archive(
            package_id=package_id, archive_bytes=body,
            expected_sha256=digest, expected_size=len(body))
        second = self.storage.store_plugin_package_archive(
            package_id=package_id, archive_bytes=body,
            expected_sha256=digest, expected_size=len(body))
        self.assertEqual(first.sha256, digest)
        self.assertEqual(first.size_bytes, len(body))
        self.assertEqual(second, first)
        self.assertEqual(self.storage.load_verified_plugin_package_archive(
            package_id=package_id, expected_sha256=digest), body)

    def test_existing_different_digest_fails_closed(self):
        package_id = uuid.uuid4()
        body = b"first archive"
        self.storage.store_plugin_package_archive(
            package_id=package_id, archive_bytes=body,
            expected_sha256=hashlib.sha256(body).digest(), expected_size=len(body))
        other = b"different archive"
        with self.assertRaises(LocalStorageError):
            self.storage.store_plugin_package_archive(
                package_id=package_id, archive_bytes=other,
                expected_sha256=hashlib.sha256(other).digest(), expected_size=len(other))

    def test_modified_stored_bytes_are_rejected(self):
        package_id = uuid.uuid4()
        body = b"verified archive"
        digest = hashlib.sha256(body).digest()
        self.storage.store_plugin_package_archive(
            package_id=package_id, archive_bytes=body,
            expected_sha256=digest, expected_size=len(body))
        _staging, final = self.storage.plugin_package_locators(package_id=package_id)
        self.storage._path(final).write_bytes(b"tampered")
        with self.assertRaises(LocalStorageError):
            self.storage.load_verified_plugin_package_archive(
                package_id=package_id, expected_sha256=digest)

    def test_invalid_identity_and_size_fail_closed(self):
        with self.assertRaises(LocalStorageError):
            self.storage.plugin_package_locators(package_id=uuid.UUID(int=0))
        body = b"wrong size"
        with self.assertRaises(LocalStorageError):
            self.storage.store_plugin_package_archive(
                package_id=uuid.uuid4(), archive_bytes=body,
                expected_sha256=hashlib.sha256(body).digest(), expected_size=len(body)-1)


if __name__ == "__main__":
    unittest.main()
