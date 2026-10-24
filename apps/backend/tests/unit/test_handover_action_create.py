from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.handover.application.create_action import (
    CreateHandoverAction, HandoverActionCreateError,
    HandoverActionCreateService, HandoverActionInitialView,
)


class HandoverActionCreateValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4(), None, "CONFIRM_DECISION",
            "Confirm scope",
            {"fields": [{
                "name": "scope", "format": "text",
                "example": "Business A", "required": True,
            }]},
            uuid.uuid4(), datetime.now(timezone.utc) + timedelta(days=7),
            "HIGH", "Project manager registered customer confirmation",
            str(uuid.uuid4()),
        )
        self.service = HandoverActionCreateService(
            unit_of_work=lambda: None, access=object(),
            license_guard=object(), authorization=object(),
            assignees=object(), repository=object(), receipts=object(),
            audit=object(),
        )

    def test_untrusted_input_fails_before_io(self):
        invalid = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"source_item_id": None},
            {"action_type": "AUTO_CLOSE"},
            {"title": " padded "},
            {"requested_input_spec": {}},
            {"requested_input_spec": {"fields": [{
                "name": "scope", "format": "text",
                "example": "", "required": True,
            }]}},
            {"owner_ref": uuid.UUID(int=0)}, {"priority": "NOW"},
            {"created_reason": " "}, {"idempotency_key": "short"},
        )
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(
                    HandoverActionCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_human_source_requires_explanation_and_no_item_identity(self):
        human = replace(
            self.command, source_analysis_version_ref=None,
            source_item_id=None, human_source_reason="Face-to-face meeting",
        )
        self.service._validate(human)
        with self.assertRaises(HandoverActionCreateError):
            self.service._validate(replace(human, human_source_reason=None))
        with self.assertRaises(HandoverActionCreateError):
            self.service._validate(replace(human, source_item_id=uuid.uuid4()))

    def test_payload_uses_utc_due_time_and_no_secret(self):
        payload = self.service._payload(self.command, "ANALYSIS_ITEM")
        self.assertEqual(payload["due_at"], self.command.due_at.isoformat())
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)

    def test_initial_view_rejects_non_open_projection(self):
        now = datetime.now(timezone.utc)
        common = (
            uuid.uuid4(), uuid.uuid4(), "HUMAN", None, None, "Meeting",
            "OTHER", "Follow up", self.command.requested_input_spec,
            uuid.uuid4(), now + timedelta(days=1), "LOW", uuid.uuid4(),
            "Manual", now, uuid.uuid4(),
        )
        HandoverActionInitialView(*common)
        with self.assertRaises(ValueError):
            HandoverActionInitialView(*common, action_state="CLOSED")


if __name__ == "__main__":
    unittest.main()
