from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.api.error_handlers import _new_uuid7
from plm_assistant.modules.platform.application.errors import (
    COMMON_ERRORS,
    ApplicationError,
)


class ErrorContractTests(unittest.TestCase):
    def test_common_codes_have_stable_statuses(self) -> None:
        self.assertEqual(COMMON_ERRORS["RESOURCE_NOT_FOUND"].status_code, 404)
        self.assertEqual(COMMON_ERRORS["SYSTEM_INTERNAL"].status_code, 500)
        self.assertEqual(COMMON_ERRORS["VALIDATION_FAILED"].status_code, 422)
        self.assertEqual(len(COMMON_ERRORS), len(set(COMMON_ERRORS)))

    def test_unknown_code_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ApplicationError("UNKNOWN_CODE")

    def test_generated_trace_id_is_canonical_uuid7(self) -> None:
        trace_id = _new_uuid7()
        parsed = uuid.UUID(trace_id)
        self.assertEqual(parsed.version, 7)
        self.assertEqual(str(parsed), trace_id)


if __name__ == "__main__":
    unittest.main()
