from __future__ import annotations

import unittest

from plm_assistant.modules.evidence.domain.eligibility import (
    EvidenceEligibilityError, EligibilityDecision, decide_eligibility,
)


class EvidenceEligibilityPolicyTests(unittest.TestCase):
    def test_actual_record_can_receive_first_human_decision(self):
        self.assertEqual(
            decide_eligibility(current_state="CANDIDATE", requested_state="ELIGIBLE",
                               reason="已核对现场调研记录与原文。",
                               document_category="PROJECT_RECORD"),
            EligibilityDecision("ELIGIBLE", "已核对现场调研记录与原文。"),
        )

    def test_template_cannot_be_formalized_as_customer_fact(self):
        with self.assertRaises(EvidenceEligibilityError) as caught:
            decide_eligibility(current_state="CANDIDATE", requested_state="ELIGIBLE",
                               reason="模板结构参考。", document_category="TEMPLATE")
        self.assertEqual(caught.exception.code, "EVIDENCE_TEMPLATE_NOT_ELIGIBLE")
        self.assertEqual(
            decide_eligibility(current_state="CANDIDATE", requested_state="INELIGIBLE",
                               reason="只是业务表单模板。", document_category="TEMPLATE").state,
            "INELIGIBLE",
        )

    def test_no_silent_redecision_or_invalid_reason(self):
        for current, requested, reason, expected in (
            ("ELIGIBLE", "INELIGIBLE", "更正", "EVIDENCE_STATE_CONFLICT"),
            ("REVOKED", "ELIGIBLE", "恢复", "EVIDENCE_STATE_CONFLICT"),
            ("CANDIDATE", "REVOKED", "原因", "VALIDATION_FAILED"),
            ("CANDIDATE", "ELIGIBLE", " 空白 ", "VALIDATION_FAILED"),
            ("CANDIDATE", "ELIGIBLE", "", "VALIDATION_FAILED"),
            ("CANDIDATE", "ELIGIBLE", "x" * 1025, "VALIDATION_FAILED"),
            ("CANDIDATE", "ELIGIBLE", "换行\n注入", "VALIDATION_FAILED"),
        ):
            with self.subTest(current=current, requested=requested, reason=reason):
                with self.assertRaises(EvidenceEligibilityError) as caught:
                    decide_eligibility(current_state=current, requested_state=requested,
                                       reason=reason, document_category="PROJECT_RECORD")
                self.assertEqual(caught.exception.code, expected)

        with self.assertRaises(EvidenceEligibilityError) as caught:
            decide_eligibility(current_state="CANDIDATE", requested_state="ELIGIBLE",
                               reason="已核对", document_category="UNKNOWN")
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
