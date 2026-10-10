from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.append_provider_config import (
    AIProviderAppendError, AIProviderAppendService, AppendAIProviderConfig,
    AppendedAIProviderConfigResult,
    PatchAIProviderConfig,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind


class AIProviderAppendValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = AppendAIProviderConfig(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), 0,
            ProviderKind.OPENAI_COMPATIBLE, "Synthetic Provider",
            "endpoint.synthetic.v2", uuid.uuid4(), "cn-beijing",
            "EXTERNAL_APPROVAL_REQUIRED", frozenset({ProviderCapability.CHAT}),
            str(uuid.uuid4()),
        )
        self.service = AIProviderAppendService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            secret_proof=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_rejects_bad_shape_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"provider_id": uuid.UUID(int=0)}, {"expected_lock_version": -1},
            {"expected_lock_version": True}, {"kind": "OPENAI_COMPATIBLE"},
            {"endpoint_policy_ref": "https://untrusted.invalid"},
            {"secret_ref": "not-a-reference"},
            {"capabilities": frozenset({"CHAT"})}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(AIProviderAppendError) as caught:
                self.service.append(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_command_does_not_echo_tokens_or_key(self) -> None:
        rendered = repr(self.command)
        self.assertNotIn("s" * 32, rendered)
        self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.command.idempotency_key, rendered)

    def test_result_shape_and_invalid_command(self) -> None:
        result = AppendedAIProviderConfigResult(self.command.provider_id, uuid.uuid4(), 2, 1)
        self.assertEqual(result.etag, '"v1"')
        with self.assertRaises(AIProviderAppendError) as caught:
            self.service.append_result(replace(self.command, expected_lock_version=True))
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_patch_rejects_uncontrolled_or_empty_changes_before_io(self) -> None:
        base = PatchAIProviderConfig(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), 0,
            {"display_name": "Synthetic Provider v2"}, str(uuid.uuid4()),
        )
        for changes in ({}, {"kind": "CUSTOM"}, {"secret_ref": "raw-key"},
                        {"capabilities": frozenset({"CHAT"})}, {"display_name": None}):
            with self.subTest(changes=changes), self.assertRaises(AIProviderAppendError) as caught:
                self.service.patch_result(replace(base, changes=changes))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
