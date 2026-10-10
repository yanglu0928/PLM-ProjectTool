from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommitUploadService, UploadCommitError,
)
from plm_assistant.modules.document.application.upload_operation_gate import UploadGateUnavailable


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

    def test_gate_contention_rejects_before_database_preflight(self) -> None:
        class BusyGate:
            def hold(self, _upload_id):
                raise UploadGateUnavailable()

        def no_transaction():
            self.fail("commit preflight must not run without the gate")

        service = CommitUploadService(
            unit_of_work=no_transaction, access=object(), repository=object(),
            receipts=object(), jobs=object(), audit=object(), storage=object(),
            license_guard=object(), operation_gate=BusyGate(),
        )
        with self.assertRaises(UploadCommitError) as raised:
            service.commit(self.command, idempotency_key="commit-gate-contention")
        self.assertEqual(raised.exception.code, "FILE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
