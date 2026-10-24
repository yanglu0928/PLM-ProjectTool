from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.prototype.application.read_identities import (
    PrototypeIdentityReadError, PrototypeIdentityReadQuery,
    PrototypeIdentityReadService, PrototypePackageSummary,
    PrototypePackageView, PrototypeSummary,
)


class _Tx:
    def __enter__(self): return self
    def __exit__(self, *_args): return False


class PrototypeIdentityReadTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.package, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.access, self.guard, self.authorization, self.repo = (
            Mock(), Mock(), Mock(), Mock(unsafe=True),
        )
        self.access.authenticated_user.return_value = self.actor
        self.authorization.require_in_transaction.side_effect = (
            lambda _tx, **kwargs: AuthorizedProjectAction(
                kwargs["user_id"], kwargs["project_id"], kwargs["operation"],
                "CUSTOMER_MEMBER",
            )
        )
        self.package_summary = PrototypePackageSummary(
            self.package, self.project, "Package", "ACTIVE", self.actor,
            self.now, None, self.now, '"v0"',
        )
        self.prototype_summary = PrototypeSummary(
            self.prototype, self.project, "Prototype", "ACTIVE", None,
            self.actor, self.now, None, self.now, '"v0"',
        )
        self.service = PrototypeIdentityReadService(
            unit_of_work=_Tx, access=self.access, license_guard=self.guard,
            authorization=self.authorization, repository=self.repo,
            clock=lambda: self.now,
        )
        self.query = PrototypeIdentityReadQuery(
            b"s" * 32, uuid.uuid4(), self.project,
        )

    def test_package_list_is_authorized_and_stably_paged(self):
        older = PrototypePackageSummary(
            uuid.uuid4(), self.project, "Older", "RESTRICTED", self.actor,
            self.now, self.actor, self.now, '"v1"',
        )
        self.repo.list_packages.return_value = (self.package_summary, older)
        page = self.service.list_packages(self.query, page_size=1)
        self.assertEqual(page.items, (self.package_summary,))
        self.assertTrue(page.has_more)
        self.assertEqual(
            (page.next_updated_at, page.next_prototype_package_id),
            (self.now, self.package),
        )
        self.authorization.require_in_transaction.assert_called_with(
            unittest.mock.ANY, user_id=self.actor, project_id=self.project,
            operation="PRT_PACKAGE_LIST",
        )

    def test_package_get_returns_sorted_current_members(self):
        members = tuple(sorted((self.prototype, uuid.uuid4()), key=lambda x: x.bytes))
        view = PrototypePackageView(self.package_summary, members)
        self.repo.get_package.return_value = view
        self.assertEqual(self.service.get_package(self.query, self.package), view)

    def test_package_get_rejects_untrusted_member_projection(self):
        members = (self.prototype, self.prototype)
        self.repo.get_package.return_value = PrototypePackageView(
            self.package_summary, members,
        )
        with self.assertRaises(PrototypeIdentityReadError) as caught:
            self.service.get_package(self.query, self.package)
        self.assertEqual(caught.exception.code, "PROTOTYPE_UNAVAILABLE")

    def test_prototype_list_and_get_use_distinct_operations(self):
        self.repo.list_prototypes.return_value = (self.prototype_summary,)
        page = self.service.list_prototypes(self.query, page_size=2)
        self.assertEqual(page.items, (self.prototype_summary,))
        self.assertFalse(page.has_more)
        self.repo.get_prototype.return_value = self.prototype_summary
        self.assertEqual(
            self.service.get_prototype(self.query, self.prototype),
            self.prototype_summary,
        )
        operations = [call.kwargs["operation"]
                      for call in self.authorization.require_in_transaction.call_args_list]
        self.assertEqual(operations, ["PRT_LIST", "PRT_GET"])

    def test_missing_or_cross_project_identity_is_hidden(self):
        self.repo.get_prototype.return_value = None
        with self.assertRaises(PrototypeIdentityReadError) as caught:
            self.service.get_prototype(self.query, self.prototype)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_invalid_cursor_position_and_secret_repr_are_rejected(self):
        with self.assertRaises(PrototypeIdentityReadError) as caught:
            self.service.list_packages(
                self.query, page_size=1, after_updated_at=self.now,
                after_prototype_package_id=None,
            )
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertNotIn("s" * 32, repr(self.query))


if __name__ == "__main__":
    unittest.main()
