from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.create_model import (
    AIModelCreateError, AIModelCreateService, CreateAIModel,
)
from plm_assistant.modules.ai.domain.model_definition import AIModelKind


class AIModelCreateValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreateAIModel(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), "model-1",
            AIModelKind.EMBEDDING, "PROVIDER_MANAGED", 1024, False, 8192,
            (), str(uuid.uuid4()),
        )
        self.service = AIModelCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            repository=object(), receipts=object(), audit=object(),
        )

    def test_untrusted_input_fails_before_database_or_license(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"provider_id": uuid.UUID(int=0)},
            {"kind": "EMBEDDING"}, {"provider_model_key": "https://unsafe/?key=x"},
            {"embedding_dimension": None}, {"embedding_dimension": 0},
            {"embedding_dimension": True}, {"structured_output": True},
            {"context_window_tokens": True}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(AIModelCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_unproved_quality_reference_is_rejected_before_io(self) -> None:
        with self.assertRaises(AIModelCreateError) as caught:
            self.service.create(replace(self.command, quality_profile_refs=("quality.synthetic.v1",)))
        self.assertEqual(caught.exception.code, "AI_MODEL_QUALITY_UNVERIFIED")

    def test_tokens_are_redacted_from_command_repr(self) -> None:
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn("c" * 32, repr(self.command))


if __name__ == "__main__":
    unittest.main()
