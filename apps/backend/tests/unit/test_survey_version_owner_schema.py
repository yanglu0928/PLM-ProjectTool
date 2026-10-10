from __future__ import annotations

import importlib
import inspect
import unittest


class SurveyVersionOwnerSchemaTests(unittest.TestCase):
    def test_owner_guard_is_narrow_and_downgrade_is_history_safe(self):
        module = importlib.import_module(
            "plm_assistant.migrations.versions.20261006_0104_survey_version_owner"
        )
        guard = module._OWNER_GUARD
        self.assertIn("NEW.lock_version=OLD.lock_version+1", guard)
        self.assertIn(
            "NEW.current_approved_version_ref IS NOT DISTINCT FROM OLD.current_approved_version_ref",
            guard,
        )
        self.assertNotIn("NEW.current_approved_version_ref IS NULL", guard)
        self.assertIn("NEW.name=OLD.name", guard)
        self.assertIn("Survey Owner transition is invalid", guard)
        self.assertIn("srv_survey_versions", inspect.getsource(module.downgrade))


if __name__ == "__main__":
    unittest.main()
