from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage, ParseResultStorageError,
)


class ParseResultStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = LocalParseResultStorage(self.root)
        self.project_id = uuid.uuid4()
        self.result_id = uuid.uuid4()
        self.content = b'{"schema_version":"1","nodes":[]}'

    def test_write_once_and_verified_read_are_scope_bound(self) -> None:
        for scope, project in (("GLOBAL", None), ("PROJECT", self.project_id)):
            with self.subTest(scope=scope):
                result_id = uuid.uuid4()
                stored = self.storage.write_once(scope=scope, project_id=project,
                    result_ref_id=result_id, content=self.content)
                self.assertEqual(stored.sha256, hashlib.sha256(self.content).digest())
                self.assertFalse(stored.storage_locator.startswith("temp/"))
                self.assertFalse(Path(stored.storage_locator).is_absolute())
                self.assertEqual(self.storage.read_verified(
                    scope=scope, project_id=project, result_ref_id=result_id,
                    expected_locator=stored.storage_locator,
                    expected_sha256=stored.sha256, expected_size=stored.size_bytes),
                    self.content)
                wrong_scope = "PROJECT" if scope == "GLOBAL" else "GLOBAL"
                wrong_project = self.project_id if wrong_scope == "PROJECT" else None
                with self.assertRaises(ParseResultStorageError):
                    self.storage.read_verified(scope=wrong_scope,
                        project_id=wrong_project,
                        result_ref_id=result_id, expected_locator=stored.storage_locator,
                        expected_sha256=stored.sha256, expected_size=stored.size_bytes)

    def test_repeated_id_never_overwrites_original_and_tamper_rejected(self) -> None:
        stored = self.storage.write_once(scope="PROJECT", project_id=self.project_id,
            result_ref_id=self.result_id, content=self.content)
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="PROJECT", project_id=self.project_id,
                result_ref_id=self.result_id, content=b"different result")
        final = self.root / Path(*stored.storage_locator.split("/"))
        self.assertEqual(final.read_bytes(), self.content)
        final.write_bytes(b"tampered result")
        with self.assertRaises(ParseResultStorageError):
            self.storage.read_verified(scope="PROJECT", project_id=self.project_id,
                result_ref_id=self.result_id, expected_locator=stored.storage_locator,
                expected_sha256=stored.sha256, expected_size=stored.size_bytes)

    def test_invalid_coordinates_rejected(self) -> None:
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="PROJECT", project_id=None,
                result_ref_id=self.result_id, content=self.content)
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="GLOBAL", project_id=self.project_id,
                result_ref_id=self.result_id, content=self.content)
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="GLOBAL", project_id=None,
                result_ref_id=self.result_id, content=b"")

    def test_untrusted_directory_rejected(self) -> None:
        (self.root / "results").write_bytes(b"not a directory")
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="GLOBAL", project_id=None,
                result_ref_id=self.result_id, content=self.content)
        (self.root / "results").unlink()
        external = self.root.parent / ("outside-" + uuid.uuid4().hex)
        external.mkdir()
        self.addCleanup(lambda: external.rmdir())
        result_root = self.root / "results"
        try:
            os.symlink(external, result_root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this Windows account cannot create directory symlinks")
        with self.assertRaises(ParseResultStorageError):
            self.storage.write_once(scope="GLOBAL", project_id=None,
                result_ref_id=self.result_id, content=self.content)


if __name__ == "__main__":
    unittest.main()
