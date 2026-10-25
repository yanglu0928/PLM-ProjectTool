from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_requirement import (
    REQUIREMENT_CURSOR_KEY_REF, REQUIREMENT_PACKAGE_CURSOR_KEY_REF,
    REQUIREMENT_RELATION_CURSOR_KEY_REF, REQUIREMENT_VERSION_CURSOR_KEY_REF,
    ProductionRequirementStartupError, create_windows_requirement_routers,
)


class Keys:
    def __init__(self, missing=None):
        self.missing, self.refs = missing, []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        if key_ref == self.missing:
            return None
        return {
            REQUIREMENT_PACKAGE_CURSOR_KEY_REF: b"p" * 32,
            REQUIREMENT_CURSOR_KEY_REF: b"q" * 32,
            REQUIREMENT_VERSION_CURSOR_KEY_REF: b"v" * 32,
            REQUIREMENT_RELATION_CURSOR_KEY_REF: b"r" * 32,
        }[key_ref]


class WindowsRequirementCompositionTests(unittest.TestCase):
    @staticmethod
    def dependencies():
        runtime = Mock()
        runtime.unit_of_work = Mock()
        return runtime, Mock(), Mock(), Mock(), Mock()

    @staticmethod
    def operations(routers):
        values = []
        for router in (
            routers.packages, routers.requirements, routers.versions,
            routers.relations, routers.review_submission,
        ):
            if router is not None:
                values.extend(
                    (method, route.path)
                    for route in router.routes
                    for method in route.methods
                    if method not in {"HEAD", "OPTIONS"}
                )
        return values

    def test_read_mode_mounts_seven_gets_and_write_mode_all_22_operations(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        keys = Keys()
        read_only = create_windows_requirement_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=False, resolver=keys,
        )
        read_operations = self.operations(read_only)
        self.assertEqual(7, len(read_operations))
        self.assertEqual({"GET"}, {item[0] for item in read_operations})
        self.assertIsNone(read_only.review_submission)

        write = create_windows_requirement_routers(
            runtime, sessions=sessions, origins=origins, license_guard=guard,
            audit=audit, include_write=True, resolver=Keys(),
        )
        operations = self.operations(write)
        self.assertEqual(22, len(operations))
        self.assertEqual(7, sum(method == "GET" for method, _ in operations))
        self.assertEqual(15, sum(method != "GET" for method, _ in operations))
        self.assertEqual([
            REQUIREMENT_PACKAGE_CURSOR_KEY_REF, REQUIREMENT_CURSOR_KEY_REF,
            REQUIREMENT_VERSION_CURSOR_KEY_REF,
            REQUIREMENT_RELATION_CURSOR_KEY_REF,
        ], keys.refs)

    def test_missing_each_key_and_invalid_mode_fail_closed(self):
        runtime, sessions, origins, guard, audit = self.dependencies()
        for missing in (
            REQUIREMENT_PACKAGE_CURSOR_KEY_REF, REQUIREMENT_CURSOR_KEY_REF,
            REQUIREMENT_VERSION_CURSOR_KEY_REF,
            REQUIREMENT_RELATION_CURSOR_KEY_REF,
        ):
            with self.subTest(missing=missing), self.assertRaises(
                    ProductionRequirementStartupError):
                create_windows_requirement_routers(
                    runtime, sessions=sessions, origins=origins,
                    license_guard=guard, audit=audit, include_write=False,
                    resolver=Keys(missing),
                )
        with self.assertRaises(ProductionRequirementStartupError):
            create_windows_requirement_routers(
                runtime, sessions=sessions, origins=origins,
                license_guard=guard, audit=audit, include_write=1,
                resolver=Keys(),
            )


if __name__ == "__main__":
    unittest.main()
