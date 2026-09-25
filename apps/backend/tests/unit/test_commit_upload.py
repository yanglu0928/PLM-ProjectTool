from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommitUploadService, UploadCommitError,
)


class CommitUploadValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CommitUpload(
            uuid.uuid4(), "GLOBAL", None, uuid.uuid4(), uuid.uuid4(), None, 100,
        )

    def test_invalid_scope_ids_or_limit_fail_before_dependencies(self) -> None:
        for command in (
            replace(self.command, upload_id=uuid.UUID(int=0)),
            replace(self.command, scope="PROJECT"),
            replace(self.command, scope="GLOBAL", project_id=uuid.uuid4()),
            replace(self.command, expected_document_version=-1),
            replace(self.command, max_bytes=-1),
        ):
            with self.subTest(command=command), self.assertRaises(UploadCommitError):
                CommitUploadService._validate(command)


if __name__ == "__main__":
    unittest.main()
