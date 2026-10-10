from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_capability import (
    CAPABILITY_BASELINE_CURSOR_KEY_REF, CAPABILITY_CHILD_CURSOR_KEY_REF,
    ProductionCapabilityStartupError, create_windows_capability_routers,
)


class Keys:
    def __init__(self, missing: str | None = None):
        self.missing, self.refs = missing, []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        if key_ref == self.missing:
            return None
        return b"b" * 32 if key_ref == CAPABILITY_BASELINE_CURSOR_KEY_REF else b"c" * 32


class WindowsCapabilityCompositionTests(unittest.TestCase):
    def dependencies(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        return runtime, Mock(), Mock(), Mock(), Mock()

    def test_read_and_write_modes_mount_exact_router_sets(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        keys = Keys()
        read_only = create_windows_capability_routers(
            runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit, include_write=False,
            resolver=keys,
        )
        self.assertIsNotNone(read_only.reads)
        self.assertIsNone(read_only.commands)
        self.assertIsNone(read_only.review_submission)
        write = create_windows_capability_routers(
            runtime, sessions=sessions, origins=origins,
            license_guard=guard, audit=audit, include_write=True,
            resolver=Keys(),
        )
        self.assertIsNotNone(write.reads)
        self.assertIsNotNone(write.commands)
        self.assertIsNotNone(write.review_submission)
        routes = [route for router in (
            write.reads, write.commands, write.review_submission,
        ) for route in router.routes]
        self.assertEqual(12, len(routes))
        self.assertEqual(9, len({route.path for route in routes}))
        self.assertEqual([
            CAPABILITY_BASELINE_CURSOR_KEY_REF,
            CAPABILITY_CHILD_CURSOR_KEY_REF,
        ], keys.refs)

    def test_missing_dedicated_key_and_invalid_mode_fail_closed(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        for missing in (
            CAPABILITY_BASELINE_CURSOR_KEY_REF, CAPABILITY_CHILD_CURSOR_KEY_REF,
        ):
            with self.subTest(missing=missing), self.assertRaises(
                    ProductionCapabilityStartupError):
                create_windows_capability_routers(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, include_write=False,
                    resolver=Keys(missing),
                )
        with self.assertRaises(ProductionCapabilityStartupError):
            create_windows_capability_routers(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, include_write=1,
                resolver=Keys(),
            )


if __name__ == "__main__":
    unittest.main()
