from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.capability.application.survey_source_proof import (
    CapabilitySurveySourceProof,
)
from plm_assistant.modules.document.application.survey_template_proof import SurveyTemplateProof
from plm_assistant.modules.handover.application.survey_source_proof import (
    HandoverSurveySourceProof,
)
from plm_assistant.modules.project.application.survey_source_proof import (
    SurveyTargetDepartmentProof,
)


class SurveySourceProofValueTests(unittest.TestCase):
    def test_proofs_retain_only_minimum_typed_identity(self):
        values = [uuid.uuid4() for _ in range(10)]
        handover = HandoverSurveySourceProof(*values[:4], "CONFIRMED")
        capability = CapabilitySurveySourceProof(*values[4:8], "AVAILABLE")
        department = SurveyTargetDepartmentProof(*values[8:10], "ACTIVE")
        template = SurveyTemplateProof(values[0], values[1], "GLOBAL", None, "ab" * 32)
        self.assertEqual(handover.item_state, "CONFIRMED")
        self.assertEqual(capability.item_state, "AVAILABLE")
        self.assertEqual(department.state, "ACTIVE")
        for proof in (handover, capability, department, template):
            rendered = repr(proof)
            self.assertNotIn("text", rendered.lower())
            self.assertNotIn("path", rendered.lower())


if __name__ == "__main__":
    unittest.main()
