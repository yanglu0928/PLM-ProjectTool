"""First-decision Evidence eligibility policy; never confirms a business fact itself."""

from __future__ import annotations

from dataclasses import dataclass


_SOURCE_CATEGORIES = frozenset({
    "CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
    "REFERENCE_MATERIAL", "TEMPLATE", "GENERATED_ARTIFACT", "OTHER",
})


class EvidenceEligibilityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    state: str
    reason: str


def decide_eligibility(*, current_state: str, requested_state: str,
                       reason: str, document_category: str) -> EligibilityDecision:
    """Validate a human-requested first decision against current source category."""
    if (type(current_state) is not str or type(requested_state) is not str
            or type(reason) is not str or type(document_category) is not str
            or requested_state not in ("ELIGIBLE", "INELIGIBLE")
            or document_category not in _SOURCE_CATEGORIES
            or not 1 <= len(reason) <= 1024 or reason != reason.strip()
            or any(ord(char) < 32 for char in reason)):
        raise EvidenceEligibilityError("VALIDATION_FAILED")
    if current_state != "CANDIDATE":
        raise EvidenceEligibilityError("EVIDENCE_STATE_CONFLICT")
    if document_category == "TEMPLATE" and requested_state == "ELIGIBLE":
        raise EvidenceEligibilityError("EVIDENCE_TEMPLATE_NOT_ELIGIBLE")
    return EligibilityDecision(requested_state, reason)
