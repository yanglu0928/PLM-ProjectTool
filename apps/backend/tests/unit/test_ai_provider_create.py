from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.create_provider import (
    AIProviderCreateError, AIProviderCreateService, CreateAIProvider,
)
from plm_assistant.modules.ai.domain.provider_configuration import (
    ProviderCapability, ProviderKind,
)


class AIProviderCreateValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreateAIProvider(
            b"s" * 32, b"c" * 32, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
            "Synthetic Provider", "endpoint.synthetic.v1", uuid.uuid4(),
            "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
            frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
        )
        self.service = AIProviderCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            secret_proof=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_rejects_untrusted_command_before_any_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"kind": "OPENAI_COMPATIBLE"},
            {"endpoint_policy_ref": "https://untrusted.invalid/v1"},
            {"secret_ref": "not-a-reference"},
            {"capabilities": frozenset({"CHAT"})},
            {"idempotency_key": "too-short"},
        ):
            with self.subTest(change=change), self.assertRaises(AIProviderCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_command_does_not_echo_session_or_csrf(self) -> None:
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn("c" * 32, repr(self.command))

    def test_create_view_rejects_untrusted_command_before_io(self) -> None:
        with self.assertRaises(AIProviderCreateError) as caught:
            self.service.create_view(replace(self.command, csrf_token=b"short"))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
