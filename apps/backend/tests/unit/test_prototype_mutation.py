from __future__ import annotations

import inspect
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.prototype.application.mutate_prototype import (
    ArchivePrototypeIdentity, PatchPrototypeIdentity, PrototypeIdentityView,
    PrototypeMutationError, PrototypeMutationService,
)
from plm_assistant.modules.prototype.infrastructure.prototype_mutation_repository import (
    SqlAlchemyPrototypeMutationRepository,
)


class PrototypeMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.patch = PatchPrototypeIdentity(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.prototype, 0, "Shop-floor review",
        )
        self.archive = ArchivePrototypeIdentity(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.prototype, 1, str(uuid.uuid4()),
        )
        self.service = PrototypeMutationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_patch_rejects_untrusted_input_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"prototype_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"name": ""}, {"name": "x" * 256}, {"name": "bad\x00name"},
        ):
            with self.subTest(change=change), self.assertRaises(
                PrototypeMutationError
            ) as caught:
                self.service.patch(replace(self.patch, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_archive_rejects_invalid_common_fields(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"prototype_id": uuid.UUID(int=0)},
            {"expected_version": -1},
        ):
            with self.subTest(change=change), self.assertRaises(
                PrototypeMutationError
            ) as caught:
                self.service.archive(replace(self.archive, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_only_retryable_archive_has_idempotency_key(self) -> None:
        self.assertFalse(hasattr(self.patch, "idempotency_key"))
        for command in (self.patch, self.archive):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.archive.idempotency_key, repr(self.archive))

    def test_view_accepts_preserved_approved_pointer(self) -> None:
        approved = uuid.uuid4()
        view = PrototypeIdentityView(
            self.prototype, self.project, "Scope", "ARCHIVED", approved, '"v2"',
        )
        self.assertEqual(view.current_approved_version_ref, approved)
        with self.assertRaises(ValueError):
            replace(view, prototype_state="RESTRICTED")

    def test_repository_never_deletes_history_or_membership(self) -> None:
        source = inspect.getsource(SqlAlchemyPrototypeMutationRepository.mutate)
        self.assertIn("with_for_update", source)
        self.assertIn('new_state = "ARCHIVED"', source)
        self.assertNotIn("delete(", source)
        self.assertNotIn("PrototypePackageMembershipRow", source)


if __name__ == "__main__":
    unittest.main()
