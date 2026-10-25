from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.abort_upload import (
    AbortUpload, AbortUploadService, UploadAbortError,
)
from plm_assistant.modules.document.application.upload_operation_gate import UploadGateUnavailable


class AbortUploadValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = AbortUpload(
            uuid.uuid4(), "GLOBAL", None, uuid.uuid4(), uuid.uuid4(),
        )

    def test_invalid_scope_or_ids_fail_before_dependencies(self) -> None:
        for command in (
            replace(self.command, upload_id=uuid.UUID(int=0)),
            replace(self.command, actor_id=uuid.UUID(int=0)),
            replace(self.command, trace_id=uuid.UUID(int=0)),
            replace(self.command, scope="PROJECT"),
            replace(self.command, scope="GLOBAL", project_id=uuid.uuid4()),
        ):
            with self.subTest(command=command), self.assertRaises(UploadAbortError):
                AbortUploadService._validate(command)

    def test_gate_contention_rejects_before_database_preflight(self) -> None:
        class BusyGate:
            def hold(self, _upload_id):
                raise UploadGateUnavailable()

        def no_transaction():
            self.fail("abort preflight must not run without the gate")

        service = AbortUploadService(
            unit_of_work=no_transaction, access=object(), repository=object(),
            receipts=object(), audit=object(), license_guard=object(),
            operation_gate=BusyGate(),
        )
        with self.assertRaises(UploadAbortError) as raised:
            service.abort(self.command, idempotency_key="abort-gate-contention")
        self.assertEqual(raised.exception.code, "FILE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
