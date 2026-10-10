from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.publish_file import (
    FilePublishError, FilePublishService, PublishFile,
)


class FilePublishCommandValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = PublishFile(
            uuid.uuid4(), "PROJECT", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), 0, 1024,
        )

    def test_scope_actor_and_bounds(self):
        FilePublishService._validate(self.command)
        FilePublishService._validate(replace(self.command, scope="GLOBAL", project_id=None))
        for changes in (
            dict(scope="GLOBAL"), dict(project_id=None), dict(scope="OTHER"),
            dict(expected_version=-1), dict(expected_version=True),
            dict(max_bytes=-1), dict(max_bytes=True),
            dict(actor_id=uuid.UUID(int=0)), dict(file_object_id=uuid.UUID(int=0)),
        ):
            with self.subTest(changes=changes), self.assertRaises(FilePublishError):
                FilePublishService._validate(replace(self.command, **changes))


if __name__ == "__main__":
    unittest.main()
