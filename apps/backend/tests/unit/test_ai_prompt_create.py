from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.create_prompt_template import (
    CreatePromptTemplate, PromptTemplateCreateError, PromptTemplateCreateService,
)
from plm_assistant.modules.ai.domain.prompt_identity import (
    PromptIdentityError, PromptTaskType, PromptTemplateIdentity,
)


class PromptCreateValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreatePromptTemplate(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PromptTaskType.GAP_ANALYSIS,
            str(uuid.uuid4()),
        )
        self.service = PromptTemplateCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            repository=object(), receipts=object(), audit=object(),
        )

    def test_identity_requires_frozen_task_type(self) -> None:
        for invalid in ("GAP_ANALYSIS", None, 4):
            with self.subTest(invalid=invalid), self.assertRaises(PromptIdentityError):
                PromptTemplateIdentity(uuid.uuid4(), invalid)

    def test_untrusted_input_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"task_type": "GAP_ANALYSIS"},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(PromptTemplateCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_and_key_are_redacted_from_repr(self) -> None:
        description = repr(self.command)
        self.assertNotIn("s" * 32, description)
        self.assertNotIn("c" * 32, description)
        self.assertNotIn(self.command.idempotency_key, description)


if __name__ == "__main__":
    unittest.main()
