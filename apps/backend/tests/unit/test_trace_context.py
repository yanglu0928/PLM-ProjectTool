from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.trace_context import (
    current_trace_id,
    is_canonical_uuid,
    new_uuid7,
    resolve_trace_id,
    trace_scope,
)


TRACE_A = "018f0000-0000-7000-8000-000000000001"
TRACE_B = "018f0000-0000-7000-8000-000000000002"


class TraceContextTests(unittest.TestCase):
    def test_uuid7_is_canonical(self) -> None:
        value = new_uuid7()
        self.assertTrue(is_canonical_uuid(value))
        self.assertEqual(uuid.UUID(value).version, 7)

    def test_only_exact_canonical_uuid_is_accepted(self) -> None:
        self.assertEqual(resolve_trace_id(TRACE_A), TRACE_A)
        for value in (TRACE_A.upper(), "{" + TRACE_A + "}", "not-a-uuid", None):
            with self.subTest(value=value):
                replacement = resolve_trace_id(value)
                self.assertNotEqual(replacement, value)
                self.assertEqual(uuid.UUID(replacement).version, 7)

    def test_nested_scope_restores_previous_value(self) -> None:
        self.assertIsNone(current_trace_id())
        with trace_scope(TRACE_A):
            self.assertEqual(current_trace_id(), TRACE_A)
            with trace_scope(TRACE_B):
                self.assertEqual(current_trace_id(), TRACE_B)
            self.assertEqual(current_trace_id(), TRACE_A)
        self.assertIsNone(current_trace_id())

    def test_invalid_scope_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            with trace_scope("password=private"):
                pass
        self.assertIsNone(current_trace_id())


if __name__ == "__main__":
    unittest.main()
