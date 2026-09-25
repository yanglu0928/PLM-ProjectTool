from __future__ import annotations

import os
import stat
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace

from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage, LocalStorageError, _is_reparse,
)


class LocalFileStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="plm-storage-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "data"
        self.root.mkdir()
        self.store = LocalFileStorage(self.root)
        self.project = uuid.uuid4()
        self.file_id = uuid.uuid4()

    def test_scope_bound_locators_and_no_overwrite_publish(self):
        stage, final = self.store.locators(
            scope="PROJECT", project_id=self.project,
            file_object_id=self.file_id,
        )
        self.assertTrue(stage.startswith(f"temp/projects/{self.project.hex}/"))
        self.assertEqual(final, stage.removeprefix("temp/"))
        with self.store.reserve_staging(stage) as stream:
            stream.write(b"synthetic complete content")
        with self.assertRaises(LocalStorageError):
            self.store.reserve_staging(stage)
        self.store.promote(stage, final)
        self.assertFalse((self.root / stage).exists())
        self.assertEqual((self.root / final).read_bytes(), b"synthetic complete content")
        with self.store.reserve_staging(stage) as stream:
            stream.write(b"must not overwrite")
        with self.assertRaises(LocalStorageError):
            self.store.promote(stage, final)
        self.assertEqual((self.root / final).read_bytes(), b"synthetic complete content")
        self.assertEqual((self.root / stage).read_bytes(), b"must not overwrite")

    def test_global_scope_and_invalid_uuids_rejected(self):
        stage, final = self.store.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.file_id,
        )
        self.assertTrue(stage.startswith("temp/global/objects/"))
        self.assertTrue(final.startswith("global/objects/"))
        for kwargs in (
            dict(scope="GLOBAL", project_id=self.project, file_object_id=self.file_id),
            dict(scope="PROJECT", project_id=None, file_object_id=self.file_id),
            dict(scope="PROJECT", project_id=uuid.UUID(int=0), file_object_id=self.file_id),
            dict(scope="GLOBAL", project_id=None, file_object_id=uuid.UUID(int=0)),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(LocalStorageError):
                self.store.locators(**kwargs)

    def test_path_traversal_and_unregistered_areas_rejected(self):
        with self.assertRaises(LocalStorageError):
            self.store.reserve_staging(None)
        for locator in (
            "../outside", "/tmp/outside", "C:/outside", "temp/../outside",
            "temp/global/objects/aa/" + "A" * 32,
            "plugin-data/objects/aa/" + self.file_id.hex,
            "temp/global/objects/aa/" + self.file_id.hex + "/extra",
            "temp/global/objects/aa/" + self.file_id.hex[:1] + "\\" + self.file_id.hex[2:],
        ):
            with self.subTest(locator=locator), self.assertRaises(LocalStorageError):
                self.store.reserve_staging(locator)

    def test_symlink_or_reparse_component_rejected(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        try:
            os.symlink(outside, self.root / "temp", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable for this account")
        stage, _ = self.store.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.file_id,
        )
        with self.assertRaises(LocalStorageError):
            self.store.reserve_staging(stage)
        self.assertEqual(list(outside.iterdir()), [])

    def test_root_symlink_rejected(self):
        link = Path(self.temporary.name) / "data-link"
        try:
            os.symlink(self.root, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable for this account")
        with self.assertRaises(LocalStorageError):
            LocalFileStorage(link)

    def test_reparse_flag_and_hardlink_source_rejected(self):
        self.assertTrue(_is_reparse(SimpleNamespace(
            st_mode=stat.S_IFDIR, st_file_attributes=0x400,
        )))
        stage, final = self.store.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.file_id,
        )
        with self.store.reserve_staging(stage) as stream:
            stream.write(b"synthetic")
        os.link(self.root / stage, Path(self.temporary.name) / "extra-link")
        with self.assertRaises(LocalStorageError):
            self.store.promote(stage, final)

    @unittest.skipUnless(os.name == "nt", "case aliases are Windows-specific")
    def test_windows_case_alias_directory_rejected(self):
        (self.root / "temp").mkdir()
        (self.root / "temp" / "GLOBAL").mkdir()
        stage, _ = self.store.locators(
            scope="GLOBAL", project_id=None, file_object_id=self.file_id,
        )
        with self.assertRaises(LocalStorageError):
            self.store.reserve_staging(stage)


if __name__ == "__main__":
    unittest.main()
