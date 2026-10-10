"""Human Reference eligibility decisions, separate from source qualification."""

from __future__ import annotations

import unicodedata


class ReferenceEligibilityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_TRANSITIONS = {
    "REFERENCE_ONLY": frozenset({"ELIGIBLE", "RESTRICTED", "REVOKED"}),
    "ELIGIBLE": frozenset({"RESTRICTED", "REVOKED"}),
    "RESTRICTED": frozenset({"ELIGIBLE", "REVOKED"}),
    "REVOKED": frozenset(),
}


def decide_reference_eligibility(*, current_state: str, requested_state: str,
                                 reason: str) -> None:
    if (type(current_state) is not str or type(requested_state) is not str
            or type(reason) is not str or not 1 <= len(reason) <= 2000
            or reason != reason.strip()
            or unicodedata.normalize("NFC", reason) != reason
            or any(unicodedata.category(char) == "Cc" for char in reason)):
        raise ReferenceEligibilityError("VALIDATION_FAILED")
    if requested_state not in _TRANSITIONS.get(current_state, frozenset()):
        raise ReferenceEligibilityError("CONFLICT_STATE")
