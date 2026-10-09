from __future__ import annotations

import unittest

from plm_assistant.modules.solution.domain.reference_eligibility import (
    ReferenceEligibilityError, decide_reference_eligibility,
)


class ReferenceEligibilityPolicyTests(unittest.TestCase):
    def test_allowed_human_transitions(self) -> None:
        allowed = {
            "REFERENCE_ONLY": ("ELIGIBLE", "RESTRICTED", "REVOKED"),
            "ELIGIBLE": ("RESTRICTED", "REVOKED"),
            "RESTRICTED": ("ELIGIBLE", "REVOKED"),
        }
        for old, targets in allowed.items():
            for new in targets:
                with self.subTest(old=old, new=new):
                    self.assertIsNone(decide_reference_eligibility(
                        current_state=old, requested_state=new,
                        reason="Human reviewed"))

    def test_revoked_is_terminal_and_self_transitions_are_rejected(self) -> None:
        for old in ("REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED"):
            for new in (old, "REFERENCE_ONLY"):
                with self.subTest(old=old, new=new):
                    with self.assertRaises(ReferenceEligibilityError) as captured:
                        decide_reference_eligibility(
                            current_state=old, requested_state=new,
                            reason="Human reviewed")
                    self.assertEqual(captured.exception.code, "CONFLICT_STATE")
        for new in ("ELIGIBLE", "RESTRICTED", "REVOKED"):
            with self.assertRaises(ReferenceEligibilityError) as captured:
                decide_reference_eligibility(
                    current_state="REVOKED", requested_state=new,
                    reason="Human reviewed")
            self.assertEqual(captured.exception.code, "CONFLICT_STATE")

    def test_reason_must_be_canonical_and_nonempty(self) -> None:
        for reason in ("", " trailing ", "x" * 2001, "line\nbreak", "e\u0301"):
            with self.subTest(reason=reason[:20]):
                with self.assertRaises(ReferenceEligibilityError) as captured:
                    decide_reference_eligibility(
                        current_state="REFERENCE_ONLY", requested_state="ELIGIBLE",
                        reason=reason)
                self.assertEqual(captured.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
