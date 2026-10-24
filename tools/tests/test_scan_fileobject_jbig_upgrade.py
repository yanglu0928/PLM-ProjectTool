from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scan_fileobject_jbig_upgrade import (  # noqa: E402
    LocalFileStorage, inspect_record,
)
from tools.tests.test_scan_tiff_jbig_preflight import classic  # noqa: E402


class FileObjectTiffUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = LocalFileStorage(self.root)
        self.file_id = uuid.uuid4()
        _, self.locator = self.storage.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.file_id,
        )
        self.path = self.root.joinpath(*self.locator.split("/"))
        self.path.parent.mkdir(parents=True)

    def row(self, data: bytes, **updates: object) -> SimpleNamespace:
        self.path.write_bytes(data)
        fields = dict(file_object_id=self.file_id, scope="GLOBAL", project_id=None,
                      storage_class="PERSISTENT", storage_locator=self.locator,
                      original_name_metadata="input.bin", sha256=hashlib.sha256(data).digest(),
                      size_bytes=len(data), detected_mime="application/octet-stream",
                      file_state="AVAILABLE")
        fields.update(updates)
        return SimpleNamespace(**fields)

    def test_byte_verified_jbig_and_non_jbig(self) -> None:
        self.assertEqual(inspect_record(self.row(classic(34661)), self.storage), "JBIG")
        self.assertEqual(inspect_record(self.row(classic(1)), self.storage), "TIFF_CLEAR")
        self.assertEqual(inspect_record(self.row(b"plain PDF"), self.storage), "NON_TIFF")

    def test_corrupt_hash_locator_and_declared_tiff_fail_closed(self) -> None:
        row = self.row(classic(1), sha256=b"\0" * 32)
        self.assertEqual(inspect_record(row, self.storage), "UNKNOWN")
        row = self.row(classic(1), storage_locator="global/objects/00/" + self.file_id.hex)
        self.assertEqual(inspect_record(row, self.storage), "UNKNOWN")
        row = self.row(b"not TIFF", detected_mime="image/tiff")
        self.assertEqual(inspect_record(row, self.storage), "UNKNOWN")

    def test_incomplete_and_removed_states(self) -> None:
        self.assertEqual(inspect_record(self.row(classic(1), file_state="STAGED"),
                         self.storage), "UNKNOWN")
        self.assertEqual(inspect_record(self.row(classic(1), file_state="CLEANUP_PENDING"),
                         self.storage), "UNKNOWN")
        self.assertEqual(inspect_record(self.row(classic(34661), file_state="REMOVED"),
                         self.storage), "TERMINAL_SKIP")


if __name__ == "__main__":
    unittest.main()
