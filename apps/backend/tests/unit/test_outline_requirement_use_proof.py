from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.requirement.application.outline_version_proof import (
    OutlineRequirementUseError, OutlineRequirementUseProofService,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)


class OutlineRequirementUseProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.requirement = uuid.uuid4()
        self.version = uuid.uuid4()
        self.tx = object()
        self.port = Mock()
        self.port.prove.return_value = PrototypeApprovedRequirementVersionProof(
            self.project, self.requirement, self.version, 2, "a" * 64,
            uuid.uuid4(), uuid.uuid4())
        self.service = OutlineRequirementUseProofService(approved_versions=self.port)

    def prove(self):
        return self.service.prove(
            self.tx, project_id=self.project,
            requirement_id=self.requirement,
            requirement_version_id=self.version)

    def test_current_approved_proof_returns_no_content(self) -> None:
        result = self.prove()
        self.assertEqual(result.requirement_version_id, self.version)
        self.assertEqual(result.content_fingerprint, b"\xaa" * 32)
        self.assertNotIn("aa" * 32, repr(result))
        self.port.prove.assert_called_once_with(
            self.tx, project_id=self.project,
            requirement_id=self.requirement,
            requirement_version_id=self.version)

    def test_mismatched_identity_and_port_unavailable_fail_closed(self) -> None:
        base = self.port.prove.return_value
        for changed in (
            None,
            replace(base, project_id=uuid.uuid4()),
            replace(base, requirement_id=uuid.uuid4()),
            replace(base, requirement_version_id=uuid.uuid4()),
        ):
            with self.subTest(changed=changed):
                self.port.prove.return_value = changed
                with self.assertRaises(OutlineRequirementUseError):
                    self.prove()

    def test_invalid_input_and_repository_exception_fail_closed(self) -> None:
        with self.assertRaisesRegex(OutlineRequirementUseError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, project_id=uuid.UUID(int=0),
                               requirement_id=self.requirement,
                               requirement_version_id=self.version)
        self.port.prove.side_effect = RuntimeError("repository down")
        with self.assertRaisesRegex(OutlineRequirementUseError, "REQUIREMENT_UNAVAILABLE"):
            self.prove()


if __name__ == "__main__":
    unittest.main()
