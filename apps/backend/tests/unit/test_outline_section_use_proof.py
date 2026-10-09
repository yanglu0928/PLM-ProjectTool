from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.solution.application.prove_outline_section_use import (
    OutlineSectionUseError, OutlineSectionUseProofService,
)
from plm_assistant.modules.solution.application.read_section import SectionCurrentView


class OutlineSectionUseProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.outline = uuid.uuid4()
        self.section = uuid.uuid4()
        self.tx = object()
        self.port = Mock()
        self.port.get_current.return_value = SectionCurrentView(
            self.section, self.outline, self.project, "overview", "ACTIVE",
            None, uuid.uuid4(), datetime.now(timezone.utc), '"v0"')
        self.service = OutlineSectionUseProofService(sections=self.port)

    def prove(self):
        return self.service.prove(
            self.tx, project_id=self.project,
            outline_id=self.outline, section_id=self.section)

    def test_active_stable_identity_without_approved_section_version(self) -> None:
        proof = self.prove()
        self.assertEqual(proof.solution_section_id, self.section)
        self.assertEqual(proof.solution_outline_id, self.outline)
        self.port.get_current.assert_called_once_with(
            self.tx, project_id=self.project, section_id=self.section)

    def test_scope_parent_and_archived_fail_closed(self) -> None:
        base = self.port.get_current.return_value
        for altered in (
            None,
            replace(base, project_id=uuid.uuid4()),
            replace(base, solution_outline_id=uuid.uuid4()),
            replace(base, solution_section_id=uuid.uuid4()),
            replace(base, section_state="ARCHIVED"),
        ):
            with self.subTest(altered=altered):
                self.port.get_current.return_value = altered
                with self.assertRaises(OutlineSectionUseError):
                    self.prove()

    def test_invalid_input_and_repository_failure_fail_closed(self) -> None:
        with self.assertRaisesRegex(OutlineSectionUseError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, project_id=self.project,
                               outline_id=uuid.UUID(int=0), section_id=self.section)
        self.port.get_current.side_effect = RuntimeError("repository unavailable")
        with self.assertRaisesRegex(OutlineSectionUseError, "SECTION_UNAVAILABLE"):
            self.prove()


if __name__ == "__main__":
    unittest.main()
