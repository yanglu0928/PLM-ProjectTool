from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, PromptVersionAppendError, PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft, PromptVersionError


class PromptVersionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template_id = uuid.uuid4()
        self.draft = PromptVersionDraft(
            self.template_id, PromptTaskType.GAP_ANALYSIS,
            "Synthetic system instruction\r\nUse {context}.",
            "Synthetic user question: {input}",
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
        )
        self.command = AppendPromptVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.template_id,
            PromptTaskType.GAP_ANALYSIS, self.draft.system_template,
            self.draft.user_template, self.draft.output_schema_ref,
            self.draft.schema_version, self.draft.rag_policy_ref,
            self.draft.provider_policy_ref, 0, str(uuid.uuid4()),
        )
        self.service = PromptVersionAppendService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            admission=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_canonical_newlines_and_unicode_have_same_fingerprint(self) -> None:
        self.assertEqual(self.draft.system_template, "Synthetic system instruction\nUse {context}.")
        alternate = replace(self.draft, system_template="Synthetic system instruction\nUse {context}.")
        self.assertEqual(self.draft.fingerprint, alternate.fingerprint)
        self.assertEqual(len(self.draft.system_hash), 64)

    def test_metadata_and_content_change_fingerprint(self) -> None:
        self.assertNotEqual(self.draft.fingerprint,
                            replace(self.draft, schema_version=2).fingerprint)
        self.assertNotEqual(self.draft.fingerprint,
                            replace(self.draft, user_template="Different {input}").fingerprint)

    def test_obvious_secret_and_unsafe_format_rejected(self) -> None:
        for text in (" ", "line\rbreak", "bad\u202e direction",
                     "sk-" + "x" * 24, "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(text=text[:8]), self.assertRaises(PromptVersionError):
                replace(self.draft, system_template=text)

    def test_untrusted_command_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"task_type": "GAP_ANALYSIS"},
            {"expected_lock_version": -1}, {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(PromptVersionAppendError) as caught:
                self.service.append(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_sensitive_content_not_in_repr(self) -> None:
        representation = repr(self.command)
        for text in ("Synthetic system instruction", "Synthetic user question",
                     "s" * 32, "c" * 32, self.command.idempotency_key):
            self.assertNotIn(text, representation)


if __name__ == "__main__":
    unittest.main()
