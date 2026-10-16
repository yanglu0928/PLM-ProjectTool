from __future__ import annotations

import inspect
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.prototype.application.mutate_package import (
    PatchPrototypePackage, PrototypePackageMutationError,
    PrototypePackageMutationService, PrototypePackageView,
    SetPrototypePackageMembers,
)
from plm_assistant.modules.prototype.infrastructure.package_mutation_repository import (
    SqlAlchemyPrototypePackageMutationRepository,
)


class PrototypePackageMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project, self.package = uuid.uuid4(), uuid.uuid4()
        self.patch = PatchPrototypePackage(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.package, 0, "Delivery prototypes",
        )
        self.members = SetPrototypePackageMembers(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project,
            self.package, 0, (uuid.uuid4(), uuid.uuid4()), str(uuid.uuid4()),
        )
        self.service = PrototypePackageMutationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_patch_rejects_untrusted_input_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"prototype_package_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"name": ""}, {"name": "x" * 256}, {"name": "bad\x00name"},
        ):
            with self.subTest(change=change), self.assertRaises(
                PrototypePackageMutationError
            ) as caught:
                self.service.patch(replace(self.patch, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_set_members_accepts_empty_but_rejects_invalid_or_duplicates(self) -> None:
        self.assertEqual(self.service._members(()), ())
        for values in (
            (uuid.UUID(int=0),),
            (self.members.prototype_ids[0],) * 2,
            tuple(uuid.uuid4() for _ in range(201)),
        ):
            with self.subTest(size=len(values)), self.assertRaises(
                PrototypePackageMutationError
            ) as caught:
                self.service.set_members(replace(self.members, prototype_ids=values))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_members_and_view_are_canonical(self) -> None:
        members = self.service._members(self.members.prototype_ids)
        self.assertEqual(members, tuple(sorted(members, key=str)))
        view = PrototypePackageView(
            self.package, self.project, "Scope", "ACTIVE", members, '"v1"',
        )
        self.assertEqual(view.member_refs, members)
        with self.assertRaises(ValueError):
            replace(view, member_refs=tuple(reversed(members)))

    def test_only_retryable_set_members_has_key(self) -> None:
        self.assertFalse(hasattr(self.patch, "idempotency_key"))
        for command in (self.patch, self.members):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
        self.assertNotIn(self.members.idempotency_key, repr(self.members))

    def test_repository_replaces_only_memberships(self) -> None:
        source = inspect.getsource(SqlAlchemyPrototypePackageMutationRepository.mutate)
        self.assertIn("delete(PrototypePackageMembershipRow)", source)
        self.assertNotIn("delete(PrototypeRow)", source)
        self.assertIn("with_for_update", source)
        self.assertIn("CONFLICT_VERSION", source)


if __name__ == "__main__":
    unittest.main()
