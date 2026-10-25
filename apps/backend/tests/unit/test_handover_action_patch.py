from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchError, HandoverActionPatchService, PatchHandoverAction,
)


class HandoverActionPatchValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = PatchHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 0,
            title="Confirm updated scope",
        )
        self.service = HandoverActionPatchService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), assignees=object(), repository=object(), audit=object(),
        )

    def test_rejects_empty_or_untrusted_partial_patch(self):
        invalid = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"project_id": uuid.UUID(int=0)}, {"action_item_id": uuid.UUID(int=0)},
            {"expected_version": -1}, {"title": " padded "}, {"title": None},
            {"title": None, "requested_input_spec": {}},
            {"title": None, "priority": "NOW"},
            {"title": None, "owner_ref": uuid.UUID(int=0)},
            {"title": None, "due_at": datetime.now()},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionPatchError) as caught:
                self.service.patch(replace(self.command, **values))
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_accepts_each_supported_partial_field(self):
        fields = (
            {"title": "Updated"},
            {"title": None, "requested_input_spec": {"fields": [{
                "name": "scope", "format": "text", "example": "A", "required": True,
            }]}},
            {"title": None, "owner_ref": uuid.uuid4()},
            {"title": None, "due_at": datetime.now(timezone.utc) + timedelta(days=1)},
            {"title": None, "priority": "URGENT"},
        )
        for values in fields:
            with self.subTest(values=values):
                self.service._validate(replace(self.command, **values))

    def test_command_repr_redacts_session_tokens(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)


if __name__ == "__main__":
    unittest.main()
