from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.plan.application.create_plan import (
    CreatePlan, PlanCreateError, PlanCreateService, PlanInitialView,
)


class PlanCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreatePlan(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            "Implementation plan", "i" * 16,
        )
        self.service = PlanCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_invalid_input_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"name": ""}, {"name": "x" * 501}, {"name": "bad\x00name"},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(PlanCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_name_normalization_and_first_view(self) -> None:
        self.assertEqual(self.service._name("  ＡＢＣ  "), "ABC")
        self.assertEqual(len(self.service._name("x" * 500)), 500)
        result = PlanInitialView(
            uuid.uuid4(), self.command.project_id, "Plan", datetime.now(timezone.utc))
        self.assertEqual((result.plan_state, result.etag), ("ACTIVE", '"v0"'))
        self.assertIsNone(result.current_approved_version_ref)
        with self.assertRaises(ValueError):
            replace(result, plan_state="APPROVED")

    def test_secrets_are_not_rendered(self) -> None:
        rendered = repr(self.command)
        for secret in ("s" * 32, "c" * 32, "i" * 16):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
