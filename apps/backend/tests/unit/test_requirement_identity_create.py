from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity,
    CreateRequirementPackage,
    RequirementIdentityCreateError,
    RequirementIdentityCreateService,
    RequirementInitialView,
    RequirementPackageInitialView,
)


class RequirementIdentityCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = CreateRequirementPackage(
            b"s" * 32,
            b"c" * 32,
            uuid.uuid4(),
            uuid.uuid4(),
            "Implementation scope",
            str(uuid.uuid4()),
        )
        self.requirement = CreateRequirementIdentity(
            b"s" * 32,
            b"c" * 32,
            uuid.uuid4(),
            self.package.project_id,
            "REQ-001",
            str(uuid.uuid4()),
        )
        self.service = RequirementIdentityCreateService(
            unit_of_work=lambda: None,
            access=object(),
            license_guard=object(),
            authorization=object(),
            repository=object(),
            receipts=object(),
            audit=object(),
        )

    def test_package_untrusted_input_fails_before_io(self) -> None:
        for change in (
            {"session_token": b"short"},
            {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
            {"name": ""},
            {"name": "x" * 256},
            {"name": "bad\u0000name"},
            {"idempotency_key": "short"},
        ):
            with self.subTest(change=change), self.assertRaises(
                RequirementIdentityCreateError
            ) as caught:
                self.service.create_package(replace(self.package, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_requirement_code_is_bounded_ascii_business_identity(self) -> None:
        for value in ("", "1-REQ", "需求-1", "REQ 1", "REQ/1", "x" * 65):
            with self.subTest(value=value), self.assertRaises(
                RequirementIdentityCreateError
            ) as caught:
                self.service.create_requirement(
                    replace(self.requirement, requirement_code=value)
                )
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_views_fix_initial_state_and_etag(self) -> None:
        now = datetime.now(timezone.utc)
        package = RequirementPackageInitialView(
            uuid.uuid4(), self.package.project_id, "Scope", now
        )
        requirement = RequirementInitialView(
            uuid.uuid4(), self.package.project_id, "REQ-001", now
        )
        self.assertEqual(package.etag, '"v0"')
        self.assertEqual(requirement.current_approved_version_ref, None)
        with self.assertRaises(ValueError):
            replace(requirement, requirement_state="DEFERRED")

    def test_secrets_and_keys_are_redacted(self) -> None:
        for command in (self.package, self.requirement):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            self.assertNotIn(command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
