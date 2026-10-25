from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from plm_assistant.entrypoints.windows_plan_version import (
    create_windows_plan_version_validation_composition,
    create_windows_plan_version_validation_router,
)


class WindowsPlanVersionValidationCompositionTests(unittest.TestCase):
    def test_router_and_review_owner_share_exact_current_evaluator_instance(self):
        service, router = Mock(), Mock()
        module = "plm_assistant.entrypoints.windows_plan_version."
        args = dict(
            runtime=Mock(), sessions=Mock(), origins=Mock(), license_guard=Mock(),
            audit=Mock(), document_storage_root=Path("D:/synthetic"),
            parse_result_storage_root=Path("D:/synthetic"), documents=Mock(),
            downloads=Mock(), parse_results=Mock(),
        )
        with patch(module + "create_windows_plan_version_validation_service",
                   return_value=service) as build, patch(
            module + "create_plan_version_validate_router", return_value=router,
        ) as route:
            actual_router, actual_service = create_windows_plan_version_validation_composition(**args)
            self.assertIs(actual_router, router)
            self.assertIs(actual_service, service)
            self.assertIs(route.call_args.kwargs["validations"], service)
            self.assertEqual(args["runtime"], build.call_args.kwargs["runtime"])

        with patch(module + "create_windows_plan_version_validation_service",
                   return_value=service), patch(
            module + "create_plan_version_validate_router", return_value=router,
        ):
            self.assertIs(create_windows_plan_version_validation_router(**args), router)


if __name__ == "__main__":
    unittest.main()
