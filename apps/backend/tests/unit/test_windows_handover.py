from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_handover import (
    HANDOVER_ANALYSIS_CURSOR_KEY_REF, HANDOVER_ITEM_CURSOR_KEY_REF,
    HANDOVER_VERSION_CURSOR_KEY_REF, ProductionHandoverStartupError,
    create_windows_handover_routers,
)


class Keys:
    def __init__(self, missing=None):
        self.missing, self.refs = missing, []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        if key_ref == self.missing:
            return None
        return {
            HANDOVER_ANALYSIS_CURSOR_KEY_REF: b"a" * 32,
            HANDOVER_VERSION_CURSOR_KEY_REF: b"v" * 32,
            HANDOVER_ITEM_CURSOR_KEY_REF: b"i" * 32,
        }[key_ref]


class WindowsHandoverCompositionTests(unittest.TestCase):
    def dependencies(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        return runtime, Mock(), Mock(), Mock(), Mock()

    def test_read_and_write_modes_mount_exact_analysis_routes(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        keys = Keys()
        read_only = create_windows_handover_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=False, resolver=keys,
        )
        self.assertEqual(5, len(read_only.reads.routes))
        self.assertIsNone(read_only.commands)
        self.assertIsNone(read_only.review_submission)
        write = create_windows_handover_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=True, resolver=Keys(),
        )
        self.assertEqual(5, len(write.reads.routes))
        self.assertEqual(5, len(write.commands.routes))
        self.assertEqual(1, len(write.review_submission.routes))
        self.assertEqual([
            HANDOVER_ANALYSIS_CURSOR_KEY_REF, HANDOVER_VERSION_CURSOR_KEY_REF,
            HANDOVER_ITEM_CURSOR_KEY_REF,
        ], keys.refs)

    def test_missing_each_key_and_invalid_mode_fail_closed(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        for missing in (
            HANDOVER_ANALYSIS_CURSOR_KEY_REF, HANDOVER_VERSION_CURSOR_KEY_REF,
            HANDOVER_ITEM_CURSOR_KEY_REF,
        ):
            with self.subTest(missing=missing), self.assertRaises(
                    ProductionHandoverStartupError):
                create_windows_handover_routers(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, include_write=False,
                    resolver=Keys(missing),
                )
        with self.assertRaises(ProductionHandoverStartupError):
            create_windows_handover_routers(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, include_write=1,
                resolver=Keys(),
            )


if __name__ == "__main__":
    unittest.main()
