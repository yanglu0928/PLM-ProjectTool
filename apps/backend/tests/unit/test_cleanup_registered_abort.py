from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.cleanup_registered_abort import (
    CleanupRegisteredAbort, CleanupRegisteredAbortService, RegisteredAbortCleanupError,
)
from plm_assistant.modules.document.application.upload_operation_gate import UploadGateUnavailable


class CleanupRegisteredAbortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CleanupRegisteredAbort(
            uuid.uuid4(), "GLOBAL", None, uuid.uuid4(), uuid.uuid4(),
        )

    def test_invalid_identity_and_scope_rejected(self) -> None:
        for command in (
            replace(self.command, upload_id=uuid.UUID(int=0)),
            replace(self.command, actor_id=uuid.UUID(int=0)),
            replace(self.command, trace_id=uuid.UUID(int=0)),
            replace(self.command, scope="PROJECT"),
            replace(self.command, scope="GLOBAL", project_id=uuid.uuid4()),
        ):
            with self.subTest(command=command), self.assertRaises(RegisteredAbortCleanupError):
                CleanupRegisteredAbortService._validate(command)

    def test_busy_gate_rejects_before_database_and_file(self) -> None:
        class BusyGate:
            def hold(self, _upload_id):
                raise UploadGateUnavailable()

        def no_transaction():
            self.fail("database must not be reached without the operation gate")

        service = CleanupRegisteredAbortService(
            unit_of_work=no_transaction, access=object(), repository=object(),
            audit=object(), storage=object(), operation_gate=BusyGate(),
        )
        with self.assertRaises(RegisteredAbortCleanupError) as raised:
            service.cleanup_one(self.command)
        self.assertEqual(raised.exception.code, "FILE_CONTENT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
