from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest import TestCase

from plm_assistant.entrypoints.windows_ai_read_cursor import (
    AI_READ_CURSOR_KEY_REF,
    ProductionAIReadCursorStartupError,
    create_windows_ai_read_cursor_codecs,
)
from plm_assistant.modules.ai.application.invocation_read import ListAIInvocations
from plm_assistant.modules.ai.application.task_read import ListAITasks


class Resolver:
    def __init__(self, value): self.value, self.refs = value, []
    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        if isinstance(self.value, Exception): raise self.value
        return self.value


class WindowsAIReadCursorTests(TestCase):
    def test_one_current_account_key_is_domain_separated(self):
        resolver = Resolver(b"k" * 32)
        codecs = create_windows_ai_read_cursor_codecs(resolver=resolver)
        project, task, item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        session, trace = b"s" * 32, uuid.uuid4()
        task_query = ListAITasks(session, trace, project, 50)
        invocation_query = ListAIInvocations(session, trace, project, task, 50)
        task_token = codecs.task.encode(
            query=task_query, before=(
                datetime.now(timezone.utc), item,
            ),
        )
        invocation_token = codecs.invocation.encode(
            query=invocation_query, before=(1, item),
        )
        self.assertEqual(resolver.refs, [AI_READ_CURSOR_KEY_REF])
        self.assertTrue(task_token.startswith("ait1."))
        self.assertTrue(invocation_token.startswith("aii1."))
        with self.assertRaises(Exception):
            codecs.task.decode(invocation_token, query=task_query)

    def test_missing_wrong_or_failed_key_fails_closed(self):
        for value in (None, b"x" * 31, RuntimeError("private key detail")):
            with self.subTest(value=type(value)), self.assertRaises(
                    ProductionAIReadCursorStartupError) as caught:
                create_windows_ai_read_cursor_codecs(resolver=Resolver(value))
            self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    import unittest
    unittest.main()
