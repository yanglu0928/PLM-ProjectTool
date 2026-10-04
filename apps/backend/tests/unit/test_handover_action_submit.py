from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.submit_action import (
    HandoverActionSubmitError, HandoverActionSubmitService,
    SubmitHandoverAction,
)


class HandoverActionSubmitValidationTests(unittest.TestCase):
    def setUp(self):
        self.document = HandoverDocumentRef(uuid.uuid4(), uuid.uuid4())
        self.command = SubmitHandoverAction(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            1, (self.document,), (uuid.uuid4(),), "Response submitted",
            "submit-key-0001",
        )

    def test_rejects_untrusted_or_incomplete_submission(self):
        invalid = (
            {"session_token": b"short"},
            {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
            {"action_item_id": uuid.UUID(int=0)},
            {"expected_version": -1},
            {"expected_version": True},
            {"response_documents": ()},
            {"response_documents": (self.document, self.document)},
            {"evidence_refs": ()},
            {"evidence_refs": (self.command.evidence_refs[0],) * 2},
            {"reason": ""},
            {"reason": " padded "},
            {"reason": "x" * 2001},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(
                    HandoverActionSubmitError) as caught:
                HandoverActionSubmitService._validate_and_payload(
                    replace(self.command, **values),
                )
            self.assertEqual("VALIDATION_FAILED", caught.exception.code)

    def test_payload_preserves_fixed_reference_order(self):
        second = HandoverDocumentRef(uuid.uuid4(), uuid.uuid4())
        evidence = (uuid.uuid4(), uuid.uuid4())
        payload = HandoverActionSubmitService._validate_and_payload(replace(
            self.command, response_documents=(second, self.document),
            evidence_refs=evidence,
        ))
        self.assertEqual(str(second.document_version_id),
                         payload["response_documents"][0]["document_version_id"])
        self.assertEqual([str(item) for item in evidence], payload["evidence_refs"])

    def test_command_repr_redacts_credentials_and_idempotency_key(self):
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn("submit-key-0001", rendered)


if __name__ == "__main__":
    unittest.main()
