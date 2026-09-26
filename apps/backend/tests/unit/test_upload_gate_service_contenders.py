from __future__ import annotations

import hashlib
import tempfile
import unittest
import uuid
from pathlib import Path

from plm_assistant.modules.document.application.abort_upload import (
    AbortUpload, AbortUploadService, UploadAbortError,
)
from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommitUploadService, UploadCommitError,
)
from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, ReceiveUploadContentService, UploadContentError,
)
from plm_assistant.modules.document.infrastructure.upload_operation_gate import LocalUploadOperationGate


class UploadGateServiceContenderTests(unittest.TestCase):
    def test_content_commit_abort_share_same_upload_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            holder, contender = LocalUploadOperationGate(root), LocalUploadOperationGate(root)
            upload_id, actor_id, trace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            body = b"%PDF-1.7\nsynthetic\n%%EOF\n"

            def no_transaction():
                self.fail("a contender must not enter its database transaction")

            content = ReceiveUploadContentService(
                unit_of_work=no_transaction, access=object(), repository=object(),
                audit=object(), spool=object(), storage=object(),
                operation_gate=contender,
            )
            commit = CommitUploadService(
                unit_of_work=no_transaction, access=object(), repository=object(),
                receipts=object(), jobs=object(), audit=object(), storage=object(),
                license_guard=object(), operation_gate=contender,
            )
            abort = AbortUploadService(
                unit_of_work=no_transaction, access=object(), repository=object(),
                receipts=object(), audit=object(), license_guard=object(),
                operation_gate=contender,
            )
            content_command = ReceiveUploadContent(
                upload_id, "GLOBAL", None, actor_id, trace_id,
                "A" * 43, len(body), hashlib.sha256(body).digest(),
            )
            commit_command = CommitUpload(upload_id, "GLOBAL", None, actor_id,
                                          trace_id, None, 100_000_000)
            abort_command = AbortUpload(upload_id, "GLOBAL", None, actor_id, trace_id)

            with holder.hold(upload_id):
                for error, action in (
                    (UploadContentError, lambda: content.receive(content_command, chunks=[body])),
                    (UploadCommitError, lambda: commit.commit(commit_command, idempotency_key="commit-contender")),
                    (UploadAbortError, lambda: abort.abort(abort_command, idempotency_key="abort-gate-contender")),
                ):
                    with self.subTest(error=error):
                        with self.assertRaises(error) as raised:
                            action()
                        self.assertEqual(raised.exception.code, "FILE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
