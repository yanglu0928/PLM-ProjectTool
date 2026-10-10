from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.change_file_state import (
    ChangeFileState, FileStateCommandError, FileStateService,
)


class FileStateCommandValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = ChangeFileState(
            file_object_id=uuid.uuid4(), scope="PROJECT", project_id=uuid.uuid4(),
            actor_id=uuid.uuid4(), trace_id=uuid.uuid4(), expected_version=0,
            target_state="FAILED", reason_code="FILE_CHECK_FAILED",
        )

    def test_only_internal_fail_or_restrict_targets_accepted(self):
        FileStateService._validate(self.command)
        FileStateService._validate(replace(self.command, target_state="RESTRICTED"))
        for values in (
            dict(target_state="AVAILABLE"), dict(target_state="CLEANUP_PENDING"),
            dict(scope="GLOBAL"), dict(project_id=None),
            dict(expected_version=-1), dict(expected_version=True),
            dict(reason_code="bad-path"), dict(reason_code=""),
            dict(file_object_id=uuid.UUID(int=0)),
        ):
            with self.subTest(values=values), self.assertRaises(FileStateCommandError):
                FileStateService._validate(replace(self.command, **values))

    def test_global_scope_requires_null_project(self):
        FileStateService._validate(replace(self.command, scope="GLOBAL", project_id=None))


if __name__ == "__main__":
    unittest.main()
