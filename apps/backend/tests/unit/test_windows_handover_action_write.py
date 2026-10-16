from __future__ import annotations

import unittest
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_handover_action import (
    ProductionHandoverActionWriteStartupError,
    create_windows_handover_action_write_routers,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService


class WindowsHandoverActionWriteCompositionTests(unittest.TestCase):
    def test_composes_all_seven_routes_with_explicit_owner_registry(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        routers = create_windows_handover_action_write_routers(
            runtime, sessions=Mock(), origins=Mock(), license_guard=Mock(),
            audit=Mock(), target_proofs=TraceTargetProofService({}),
        )
        paths = [route.path for route in (
            *routers.commands.routes, *routers.lifecycle.routes,
        )]
        root = "/api/v1/projects/{project_id}/handover-action-items"
        item = root + "/{action_item_id}"
        self.assertEqual([
            root, item, item + ":start", item + ":submit", item + ":verify",
            item + ":close", item + ":cancel",
        ], paths)

    def test_missing_dependency_fails_closed(self):
        runtime = Mock()
        runtime.unit_of_work = Mock()
        with self.assertRaises(ProductionHandoverActionWriteStartupError):
            create_windows_handover_action_write_routers(
                runtime, sessions=None, origins=Mock(), license_guard=Mock(),
                audit=Mock(),
            )


if __name__ == "__main__":
    unittest.main()
