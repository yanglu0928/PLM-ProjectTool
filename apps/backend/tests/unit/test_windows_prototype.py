from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_prototype import (
    ProductionPrototypeStartupError,
    create_windows_prototype_routers,
)
from plm_assistant.entrypoints.windows_prototype_cursor import (
    PROTOTYPE_CURSOR_KEY_REFS,
)


class Keys:
    def __init__(self, missing=None, duplicate=False):
        self.missing, self.duplicate, self.refs = missing, duplicate, []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        if key_ref == self.missing:
            return None
        if self.duplicate:
            return b"x" * 32
        return bytes([PROTOTYPE_CURSOR_KEY_REFS.index(key_ref) + 1]) * 32


class WindowsPrototypeCompositionTests(unittest.TestCase):
    @staticmethod
    def dependencies():
        runtime = Mock()
        runtime.unit_of_work = Mock()
        return runtime, Mock(), Mock(), Mock(), Mock()

    @staticmethod
    def operations(routers):
        values = []
        for router in (
            routers.packages, routers.prototypes, routers.templates,
            routers.versions, routers.links, routers.review_submission,
        ):
            if router is not None:
                values.extend(
                    (method, route.path)
                    for route in router.routes
                    for method in route.methods
                    if method not in {"HEAD", "OPTIONS"}
                )
        return values

    def test_read_mode_mounts_nine_gets_and_write_mode_all_26_operations(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        keys = Keys()
        read_only = create_windows_prototype_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=False, resolver=keys,
        )
        read_operations = self.operations(read_only)
        self.assertEqual(9, len(read_operations))
        self.assertEqual({"GET"}, {item[0] for item in read_operations})
        self.assertIsNone(read_only.review_submission)

        write = create_windows_prototype_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=True, resolver=Keys(),
        )
        operations = self.operations(write)
        self.assertEqual(26, len(operations))
        self.assertEqual(9, sum(method == "GET" for method, _ in operations))
        self.assertEqual(17, sum(method != "GET" for method, _ in operations))
        self.assertEqual(list(PROTOTYPE_CURSOR_KEY_REFS), keys.refs)

    def test_missing_or_duplicate_key_and_invalid_mode_fail_closed(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        for missing in PROTOTYPE_CURSOR_KEY_REFS:
            with self.subTest(missing=missing), self.assertRaises(
                    ProductionPrototypeStartupError):
                create_windows_prototype_routers(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, include_write=False,
                    resolver=Keys(missing=missing),
                )
        for keys, mode in ((Keys(duplicate=True), False), (Keys(), 1)):
            with self.assertRaises(ProductionPrototypeStartupError):
                create_windows_prototype_routers(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, include_write=mode,
                    resolver=keys,
                )


if __name__ == "__main__":
    unittest.main()
