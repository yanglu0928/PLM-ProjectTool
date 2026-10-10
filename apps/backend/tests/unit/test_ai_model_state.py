from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.ai.application.change_model_state import (
    AIModelStateError, AIModelStateResult, AIModelStateService, ChangeAIModelState,
)


class ModelStateTests(unittest.TestCase):
    def test_available_and_unknown_operations_are_rejected_before_dependencies(self) -> None:
        service = AIModelStateService(
            unit_of_work=lambda: object(), access=object(), license_guard=object(),
            repository=object(), receipts=object(), audit=object(),
        )
        for operation in ("AVAILABLE", "ACTIVATE", "DELETE"):
            with self.subTest(operation=operation), self.assertRaises(AIModelStateError) as caught:
                service.change(ChangeAIModelState(
                    b"a" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), 0,
                    operation, str(uuid.uuid4()),
                ))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_result_shape_cannot_claim_available_or_skip_version(self) -> None:
        values = [uuid.uuid4() for _ in range(5)]
        for operation, before, after, expected, actual in (
            ("SUSPEND", "SUSPENDED", "SUSPENDED", 0, 1),
            ("RETIRE", "SUSPENDED", "AVAILABLE", 0, 1),
            ("RETIRE", "SUSPENDED", "RETIRED", 0, 2),
        ):
            with self.subTest(operation=operation, after=after, actual=actual):
                with self.assertRaises(AIModelStateError):
                    AIModelStateResult(*values, operation, before, after, expected, actual)


if __name__ == "__main__":
    unittest.main()
