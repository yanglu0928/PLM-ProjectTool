from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.retire_prompt_template import (
    PromptRetireError, RetiredPromptTemplate,
)


class RetiredPromptTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = RetiredPromptTemplate(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            "ACTIVE", 2, "RETIRED", 4, 5,
        )

    def test_first_response_etag_and_draft_shape(self) -> None:
        self.assertEqual(self.result.etag, '"v5"')
        replace(self.result, prior_state="DRAFT", prior_active_version_no=None)

    def test_inconsistent_history_rejected(self) -> None:
        for fields in (
            {"prior_state": "ACTIVE", "prior_active_version_no": None},
            {"prior_state": "DRAFT", "prior_active_version_no": 1},
            {"state": "ACTIVE"},
            {"lock_version": 6},
        ):
            with self.subTest(fields=fields), self.assertRaises(PromptRetireError):
                replace(self.result, **fields)


if __name__ == "__main__":
    unittest.main()
