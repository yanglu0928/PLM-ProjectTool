from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class WbsTraceTypeMigrationTests(unittest.TestCase):
    def test_additive_type_and_history_safe_downgrade(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0177_wbs_trace_target_type")
        self.assertEqual(migration.down_revision, "20261019_0176")
        self.assertIn("PLN-02-WBS", inspect.getsource(migration._replace_endpoint_checks))
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WBS Trace type downgrade"):
                migration.downgrade()
        self.assertIn("WBS TraceLink history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
