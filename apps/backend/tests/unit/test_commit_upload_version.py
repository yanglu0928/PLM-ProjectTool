from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.commit_upload_version import (
    CommitUploadVersion, CommitUploadVersionService, DocumentVersionCommitError,
)


class CommitUploadVersionValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CommitUploadVersion(
            uuid.uuid4(), uuid.uuid4(), "PROJECT", uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), 0, 1024,
        )

    def test_actor_scope_and_limits(self):
        CommitUploadVersionService._validate(self.command)
        CommitUploadVersionService._validate(replace(self.command, scope="GLOBAL", project_id=None))
        for changes in (
            dict(scope="GLOBAL"), dict(project_id=None), dict(scope="OTHER"),
            dict(expected_document_version=-1), dict(expected_document_version=True),
            dict(max_bytes=-1), dict(max_bytes=True),
            dict(document_id=uuid.UUID(int=0)), dict(file_object_id=uuid.UUID(int=0)),
            dict(actor_id=uuid.UUID(int=0)),
        ):
            with self.subTest(changes=changes), self.assertRaises(DocumentVersionCommitError):
                CommitUploadVersionService._validate(replace(self.command, **changes))


if __name__ == "__main__":
    unittest.main()
