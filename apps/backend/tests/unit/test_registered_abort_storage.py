from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError


class RegisteredAbortStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="plm-abort-cleanup-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "data"
        self.root.mkdir()
        self.storage = LocalFileStorage(self.root)
        self.upload_id = uuid.uuid4()
        self.stage, self.final = self.storage.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.upload_id,
        )
        self.content = b"%PDF-1.7\nsynthetic registered abort\n%%EOF\n"
        self.sha = hashlib.sha256(self.content).digest()

    def stage_file(self) -> None:
        with self.storage.reserve_staging(self.stage) as stream:
            stream.write(self.content)

    def discard(self) -> str:
        return self.storage.discard_one_registered_aborted(
            self.stage, self.final, expected_sha256=self.sha,
            expected_size=len(self.content), max_bytes=100_000_000,
        )

    def test_stage_only_then_missing_is_retryable(self) -> None:
        self.stage_file()
        self.assertEqual(self.discard(), "STAGE_REMOVED")
        self.assertFalse((self.root / self.stage).exists())
        self.assertEqual(self.discard(), "NONE")

    def test_final_only_then_missing_is_retryable(self) -> None:
        final_path = self.root / self.final
        final_path.parent.mkdir(parents=True)
        final_path.write_bytes(self.content)
        self.assertEqual(self.discard(), "FINAL_REMOVED")
        self.assertFalse(final_path.exists())
        self.assertEqual(self.discard(), "NONE")

    def test_linked_pair_requires_two_separate_steps(self) -> None:
        self.stage_file()
        final_path = self.root / self.final
        final_path.parent.mkdir(parents=True)
        try:
            os.link(self.root / self.stage, final_path)
        except OSError:
            self.skipTest("hard-link creation unavailable")
        self.assertEqual(self.discard(), "STAGE_REMOVED")
        self.assertFalse((self.root / self.stage).exists())
        self.assertEqual(final_path.read_bytes(), self.content)
        self.assertEqual(self.discard(), "FINAL_REMOVED")
        self.assertEqual(self.discard(), "NONE")

    def test_unrelated_pair_or_corrupt_bytes_are_not_deleted(self) -> None:
        self.stage_file()
        final_path = self.root / self.final
        final_path.parent.mkdir(parents=True)
        final_path.write_bytes(self.content)
        with self.assertRaises(LocalStorageError):
            self.discard()
        self.assertTrue((self.root / self.stage).is_file())
        self.assertTrue(final_path.is_file())
        final_path.unlink()
        (self.root / self.stage).write_bytes(b"corrupt")
        with self.assertRaises(LocalStorageError):
            self.discard()
        self.assertTrue((self.root / self.stage).is_file())

    def test_extra_hardlink_denies_staging_delete(self) -> None:
        self.stage_file()
        try:
            os.link(self.root / self.stage, self.root / "unexpected-link")
        except OSError:
            self.skipTest("hard-link creation unavailable")
        with self.assertRaises(LocalStorageError):
            self.discard()
        self.assertTrue((self.root / self.stage).is_file())

    def test_identity_replacement_after_hash_does_not_delete(self) -> None:
        self.stage_file()
        replacement = self.root / "same-bytes-different-inode"
        replacement.write_bytes(self.content)
        real_verify = self.storage._verify_content

        def replace_after_proof(locator, **claims):
            result = real_verify(locator, **claims)
            os.replace(replacement, self.root / self.stage)
            return result

        with patch.object(self.storage, "_verify_content", side_effect=replace_after_proof):
            with self.assertRaises(LocalStorageError):
                self.discard()
        self.assertEqual((self.root / self.stage).read_bytes(), self.content)


if __name__ == "__main__":
    unittest.main()
