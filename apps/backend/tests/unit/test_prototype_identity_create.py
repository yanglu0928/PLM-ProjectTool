from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.prototype.application.create_identity import (
    CreatePrototypeIdentity, CreatePrototypePackage, PrototypeIdentityCreateError,
    PrototypeIdentityCreateService, PrototypeInitialView,
    PrototypePackageInitialView,
)


class PrototypeIdentityCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = CreatePrototypePackage(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(),
            "Implementation prototypes", str(uuid.uuid4()),
        )
        self.prototype = CreatePrototypeIdentity(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.package.project_id,
            "Approval workflow", str(uuid.uuid4()),
        )
        self.service = PrototypeIdentityCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_untrusted_input_fails_before_io(self) -> None:
        for command in (self.package, self.prototype):
            for change in (
                {"session_token": b"short"}, {"csrf_token": b"short"},
                {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
                {"name": ""}, {"name": "x" * 256}, {"name": "bad\x00name"},
                {"idempotency_key": "short"},
            ):
                with self.subTest(command=type(command).__name__, change=change), \
                        self.assertRaises(PrototypeIdentityCreateError) as caught:
                    method = (
                        self.service.create_package
                        if type(command) is CreatePrototypePackage
                        else self.service.create_prototype
                    )
                    method(replace(command, **change))
                self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_names_are_nfkc_normalized(self) -> None:
        self.assertEqual(self.service._name("  ＡＢＣ  "), "ABC")

    def test_views_fix_initial_state_pointer_and_etag(self) -> None:
        now = datetime.now(timezone.utc)
        package = PrototypePackageInitialView(
            uuid.uuid4(), self.package.project_id, "Scope", now,
        )
        prototype = PrototypeInitialView(
            uuid.uuid4(), self.package.project_id, "Flow", now,
        )
        self.assertEqual((package.package_state, package.etag), ("ACTIVE", '"v0"'))
        self.assertEqual(
            (prototype.prototype_state, prototype.current_approved_version_ref,
             prototype.etag),
            ("ACTIVE", None, '"v0"'),
        )
        with self.assertRaises(ValueError):
            replace(prototype, prototype_state="NOT_REQUIRED")

    def test_secrets_and_keys_are_redacted(self) -> None:
        for command in (self.package, self.prototype):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
            self.assertNotIn(command.idempotency_key, rendered)


if __name__ == "__main__":
    unittest.main()
