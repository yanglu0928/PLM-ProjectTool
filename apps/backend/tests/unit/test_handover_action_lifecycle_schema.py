from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class HandoverActionLifecycleSchemaTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261005_0099_handover_action_lifecycle"
        )

    def test_revision_and_exact_transition_matrix(self):
        self.assertEqual("20261005_0098", self.migration.down_revision)
        for required in (
            "OLD.action_state='OPEN' AND NEW.action_state='IN_PROGRESS'",
            "OLD.action_state='IN_PROGRESS' AND NEW.action_state='SUBMITTED'",
            "OLD.action_state='SUBMITTED' AND NEW.action_state='VERIFIED'",
            "OLD.action_state='VERIFIED' AND NEW.action_state='CLOSED'",
            "NEW.action_state='CANCELLED'",
            "Handover Action state transition is invalid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.migration._GUARDS)

    def test_submission_verification_and_closure_are_deferred_complete(self):
        for required in (
            "Handover Action submission is incomplete",
            "purpose='SUBMISSION'",
            "Handover Action verification is incomplete",
            "purpose='VERIFICATION'",
            "Handover Action closure is incomplete",
            "link.link_state='ACTIVE'",
            "event_count<>action_row.lock_version+1",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.migration._GUARDS)

    def test_owned_history_is_insert_only_and_current_project_scoped(self):
        for required in (
            "Handover Action response reference is immutable",
            "Handover Action evidence reference is immutable",
            "Handover Action owned reference scope is invalid",
            "version.availability_state<>'AVAILABLE'",
            "evidence.eligibility_state<>'ELIGIBLE'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_lifecycle_history(self):
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Handover Action lifecycle"):
                self.migration.downgrade()
        execute.assert_not_called()
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("Handover Action lifecycle history prevents downgrade", source)
        self.assertIn("20261005_0098_handover_action_foundation", source)


if __name__ == "__main__":
    unittest.main()
