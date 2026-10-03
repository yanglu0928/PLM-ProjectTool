from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.ai.infrastructure.task_orm import (
    AISuggestionEvidenceRefRow,
    AISuggestionPayloadRow,
)


class AISuggestionPayloadSchemaTests(unittest.TestCase):
    def test_owned_tables_bind_invocation_schema_fact_and_evidence(self) -> None:
        payload = AISuggestionPayloadRow.__table__
        evidence = AISuggestionEvidenceRefRow.__table__
        self.assertEqual(payload.schema, "plm")
        self.assertEqual(evidence.schema, "plm")
        self.assertIn("canonical_payload", payload.c)
        self.assertIn("payload_fingerprint", payload.c)
        self.assertIn("fact_status", payload.c)
        self.assertIn("content_fingerprint", evidence.c)
        self.assertTrue(any(
            item.name == "uq_ai_suggestion_payloads__invocation"
            for item in payload.constraints
        ))

    def test_guard_requires_running_unpublished_invocation(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0074_ai_suggestion_payload"
        )
        for required in (
            "invocation_row.invocation_state<>'RUNNING'",
            "invocation_row.suggestion_payload_ref IS NOT NULL",
            "schema_validation_state<>'PENDING'",
            "AI Suggestion Evidence set is sealed",
            "history cannot be truncated",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261003_0074_ai_suggestion_payload"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline AI SuggestionPayload"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
