from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, HandoverAnalysisItemDraft,
    HandoverCapabilityItemRef, HandoverItemOptionDraft,
    HandoverVersionCreateError, HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef


def item(*, item_type="NEED_CONFIRM", source_missing=False, evidence=True):
    need = item_type == "NEED_CONFIRM"
    return HandoverAnalysisItemDraft(
        uuid.uuid4(), item_type, "Confirm scope", "Scope is unclear",
        "Delivery is affected", "HIGH", "HIGH",
        "Approve option A" if need else "Resolve from evidence",
        "Which scope is approved?" if need else None,
        {"fields": [{"name": "scope", "format": "text", "example": "A",
                     "required": True}]} if need else {},
        source_missing, (uuid.uuid4(),) if evidence else (),
        (HandoverCapabilityItemRef(uuid.uuid4()),),
        (HandoverItemOptionDraft("A", "Option A"),
         HandoverItemOptionDraft("B", "Option B")) if need else (),
    )


class HandoverVersionCreateValidationTests(unittest.TestCase):
    def setUp(self):
        self.command = CreateHandoverVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 0,
            (HandoverDocumentRef(uuid.uuid4(), uuid.uuid4()),),
            uuid.uuid4(), uuid.uuid4(), (item(),), (), str(uuid.uuid4()),
        )
        self.service = HandoverVersionCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), sources=object(), evidence=object(),
            capabilities=object(), ai_tasks=object(), repository=object(),
            receipts=object(), audit=object(),
        )

    def assert_invalid(self, command):
        with self.assertRaises(HandoverVersionCreateError) as caught:
            self.service.create(command)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_untrusted_envelope_fails_before_io(self):
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"expected_lock_version": -1}, {"source_documents": ()},
            {"items": ()}, {"ai_task_refs": (uuid.UUID(int=0),)},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change):
                self.assert_invalid(replace(self.command, **change))

    def test_need_confirm_requires_complete_guidance(self):
        original = self.command.items[0]
        for changed in (
            replace(original, recommendation=None),
            replace(original, confirmation_question=None),
            replace(original, options=original.options[:1]),
            replace(original, required_input_spec={"fields": [{"name": "scope"}]}),
        ):
            with self.subTest(changed=changed):
                self.assert_invalid(replace(self.command, items=(changed,)))

    def test_evidence_or_explicit_missing_source_is_required(self):
        self.assert_invalid(replace(self.command, items=(item(
            item_type="GAP", evidence=False, source_missing=False,
        ),)))
        payload = self.service._validate_and_payload(replace(
            self.command, items=(item(
                item_type="MISSING", evidence=False, source_missing=True,
            ),),
        ))
        self.assertTrue(payload["items"][0]["source_missing"])

    def test_tokens_fingerprints_and_key_are_not_rendered(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
