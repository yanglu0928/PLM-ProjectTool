from __future__ import annotations

import unittest

from plm_assistant.modules.document.domain.file_state import (
    FILE_STATES, FileStateTransitionError, transition_requirements,
)


class FileStatePolicyTests(unittest.TestCase):
    def test_exact_frozen_graph_for_each_storage_class(self):
        expected = {
            ("STAGED", "AVAILABLE"),
            ("STAGED", "FAILED"),
            ("FAILED", "CLEANUP_PENDING"),
            ("CLEANUP_PENDING", "REMOVED"),
            ("AVAILABLE", "RESTRICTED"),
        }
        for storage_class in ("PERSISTENT", "TEMPORARY"):
            allowed = expected | ({("AVAILABLE", "CLEANUP_PENDING")}
                                  if storage_class == "TEMPORARY" else set())
            for source in FILE_STATES:
                for target in FILE_STATES:
                    with self.subTest(storage_class=storage_class, source=source,
                                      target=target):
                        if (source, target) in allowed:
                            transition_requirements(
                                from_state=source, to_state=target,
                                storage_class=storage_class,
                            )
                        else:
                            with self.assertRaises(FileStateTransitionError):
                                transition_requirements(
                                    from_state=source, to_state=target,
                                    storage_class=storage_class,
                                )

    def test_external_proofs_are_exposed_but_not_claimed_satisfied(self):
        available = transition_requirements(
            from_state="STAGED", to_state="AVAILABLE", storage_class="PERSISTENT",
        )
        self.assertTrue(available.verify_final_content)
        self.assertFalse(available.verify_cleanup_eligibility)
        self.assertFalse(available.record_reason)
        cleanup = transition_requirements(
            from_state="FAILED", to_state="CLEANUP_PENDING",
            storage_class="PERSISTENT",
        )
        self.assertFalse(cleanup.verify_final_content)
        self.assertTrue(cleanup.verify_cleanup_eligibility)
        self.assertTrue(cleanup.record_reason)

    def test_unknown_state_or_storage_class_fails_closed(self):
        for values in (
            dict(from_state="staged", to_state="AVAILABLE", storage_class="PERSISTENT"),
            dict(from_state="STAGED", to_state="AVAILABLE", storage_class="persistent"),
            dict(from_state="STAGED", to_state="AVAILABLE", storage_class="UNKNOWN"),
            dict(from_state="STAGED", to_state="", storage_class="PERSISTENT"),
            dict(from_state=[], to_state="AVAILABLE", storage_class="PERSISTENT"),
        ):
            with self.subTest(values=values), self.assertRaises(FileStateTransitionError):
                transition_requirements(**values)


if __name__ == "__main__":
    unittest.main()
