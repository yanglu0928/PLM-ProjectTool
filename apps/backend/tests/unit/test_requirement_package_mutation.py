from __future__ import annotations

import inspect
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.requirement.application.mutate_package import (
    ChangeRequirementPackageMembers,
    PatchRequirementPackage,
    RequirementPackageMutationError,
    RequirementPackageMutationService,
    RequirementPackageView,
)
from plm_assistant.modules.requirement.infrastructure.package_mutation_repository import (
    SqlAlchemyRequirementPackageMutationRepository,
)


class RequirementPackageMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.package = uuid.uuid4()
        self.patch = PatchRequirementPackage(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.package,
            0, name="Delivery scope",
        )
        self.members = ChangeRequirementPackageMembers(
            b"s" * 32, b"c" * 32, uuid.uuid4(), self.project, self.package,
            0, (uuid.uuid4(), uuid.uuid4()), str(uuid.uuid4()),
        )
        self.service = RequirementPackageMutationService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            authorization=object(), repository=object(), receipts=object(), audit=object(),
        )

    def test_patch_rejects_untrusted_or_empty_change_before_io(self) -> None:
        for change in (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"project_id": uuid.UUID(int=0)},
            {"requirement_package_id": uuid.UUID(int=0)}, {"expected_version": -1},
            {"name": ""}, {"name": "x" * 256}, {"name": "bad\x00name"},
            {"name": None, "package_state": None}, {"package_state": "DELETED"},
        ):
            with self.subTest(change=change), self.assertRaises(
                RequirementPackageMutationError
            ) as caught:
                self.service.patch(replace(self.patch, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_members_are_nonempty_bounded_unique_uuids(self) -> None:
        bad_values = ((), (uuid.UUID(int=0),), (self.members.requirement_ids[0],) * 2,
                      tuple(uuid.uuid4() for _ in range(201)))
        for value in bad_values:
            with self.subTest(size=len(value)), self.assertRaises(
                RequirementPackageMutationError
            ) as caught:
                self.service.add_members(replace(self.members, requirement_ids=value))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_members_are_canonicalized_for_repository_and_fingerprint(self) -> None:
        ordered = self.service._members(self.members)
        self.assertEqual(ordered, tuple(sorted(self.members.requirement_ids, key=str)))

    def test_view_requires_sorted_unique_members_and_version_etag(self) -> None:
        members = tuple(sorted(self.members.requirement_ids, key=str))
        view = RequirementPackageView(
            self.package, self.project, "Scope", "ACTIVE", members, '"v1"'
        )
        self.assertEqual(view.member_refs, members)
        with self.assertRaises(ValueError):
            replace(view, member_refs=tuple(reversed(members)))
        with self.assertRaises(ValueError):
            replace(view, etag="v1")

    def test_secrets_are_redacted_and_only_retryable_commands_have_keys(self) -> None:
        for command in (self.patch, self.members):
            rendered = repr(command)
            self.assertNotIn("s" * 32, rendered)
            self.assertNotIn("c" * 32, rendered)
        self.assertFalse(hasattr(self.patch, "idempotency_key"))
        self.assertNotIn(self.members.idempotency_key, repr(self.members))

    def test_repository_contract_never_deletes_requirement_rows(self) -> None:
        source = inspect.getsource(SqlAlchemyRequirementPackageMutationRepository.mutate)
        self.assertIn("delete(RequirementPackageMembershipRow)", source)
        self.assertNotIn("delete(RequirementRow)", source)
        self.assertIn("with_for_update", source)
        self.assertIn("CONFLICT_VERSION", source)


if __name__ == "__main__":
    unittest.main()
