from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_handover_action_read import (
    HANDOVER_ACTION_CURSOR_KEY_REF,
    ProductionHandoverActionReadStartupError,
    create_windows_handover_action_read_router,
)


class Keys:
    def __init__(self, value: bytes | None = b"h" * 32) -> None:
        self.value, self.refs = value, []

    def resolve_key(self, key_ref: str) -> bytes | None:
        self.refs.append(key_ref)
        return self.value


class WindowsHandoverActionReadCompositionTests(unittest.TestCase):
    def test_composes_two_read_routes_with_dedicated_key(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        keys = Keys()
        router = create_windows_handover_action_read_router(
            runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
            resolver=keys,
        )
        self.assertEqual([
            "/api/v1/projects/{project_id}/handover-action-items",
            "/api/v1/projects/{project_id}/handover-action-items/{action_item_id}",
        ], [route.path for route in router.routes])
        self.assertEqual([HANDOVER_ACTION_CURSOR_KEY_REF], keys.refs)

    def test_missing_or_invalid_key_and_dependency_fail_closed(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        for key in (None, b"short"):
            with self.subTest(key=key), self.assertRaises(
                    ProductionHandoverActionReadStartupError):
                create_windows_handover_action_read_router(
                    runtime, sessions=Mock(), origins=Mock(),
                    license_guard=Mock(), resolver=Keys(key),
                )
        with self.assertRaises(ProductionHandoverActionReadStartupError):
            create_windows_handover_action_read_router(
                None, sessions=Mock(), origins=Mock(), license_guard=Mock(),
                resolver=Keys(),
            )


if __name__ == "__main__":
    unittest.main()
