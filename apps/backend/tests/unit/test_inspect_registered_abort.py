from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

from plm_assistant.modules.document.application.inspect_registered_abort import (
    InspectRegisteredAbortService, RegisteredAbortCandidate,
    RegisteredAbortInspectionError,
)
from plm_assistant.modules.document.application.upload_operation_gate import UploadGateUnavailable
from plm_assistant.modules.document.infrastructure.local_storage import LocalStorageError


class InspectRegisteredAbortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.upload_id = uuid.uuid4()
        self.candidate = RegisteredAbortCandidate(
            self.upload_id, "GLOBAL", None, "temp/global/objects/aa/" + self.upload_id.hex,
            "global/objects/aa/" + self.upload_id.hex, b"h" * 32, 12, 2, 3,
        )

    def service(self, *, shape="STAGE_ONLY", changed=False, bad_file=False, busy=False):
        candidate = self.candidate

        class Gate:
            active = False

            @contextmanager
            def hold(self, _upload_id):
                if busy:
                    raise UploadGateUnavailable()
                self.active = True
                try:
                    yield
                finally:
                    self.active = False

        gate = Gate()

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Repository:
            calls = 0

            def candidate(self, _tx, upload_id):
                assert gate.active and upload_id == candidate.upload_id
                self.calls += 1
                if changed and self.calls == 2:
                    return None
                return candidate

        class Storage:
            def inspect_recovery(self, *_args, **_kwargs):
                assert gate.active
                return SimpleNamespace(shape=shape)

            def verify_content(self, *_args, **_kwargs):
                assert gate.active
                if bad_file:
                    raise LocalStorageError()
                return object()

        return (InspectRegisteredAbortService(
            unit_of_work=Transaction, repository=Repository(),
            storage=Storage(), operation_gate=gate,
        ), gate)

    def test_verified_only_after_second_database_check(self) -> None:
        service, gate = self.service()
        result = service.inspect(self.upload_id)
        self.assertEqual(result.shape, "STAGE_VERIFIED")
        self.assertTrue(result.eligible)
        self.assertFalse(gate.active)

    def test_ambiguous_or_changed_candidate_is_not_eligible(self) -> None:
        for settings, expected in (
            ({"shape": "FINAL_VERIFIED"}, "FINAL_VERIFIED"),
            ({"changed": True}, "DB_CHANGED"),
            ({"bad_file": True}, "STAGE_INVALID"),
        ):
            with self.subTest(expected=expected):
                service, gate = self.service(**settings)
                result = service.inspect(self.upload_id)
                self.assertEqual(result.shape, expected)
                self.assertFalse(result.eligible)
                self.assertFalse(gate.active)

    def test_busy_gate_rejects_without_database_read(self) -> None:
        service, _ = self.service(busy=True)
        with self.assertRaises(RegisteredAbortInspectionError):
            service.inspect(self.upload_id)


if __name__ == "__main__":
    unittest.main()
