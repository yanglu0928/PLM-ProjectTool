from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadError, RequirementIdentityReadQuery,
    RequirementIdentityReadService, RequirementPackagePage,
    RequirementPackageSummary, RequirementPackageView, RequirementPage,
    RequirementSummary,
)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class RequirementIdentityReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.package_id, self.requirement_id = uuid.uuid4(), uuid.uuid4()
        self.now = datetime.now(timezone.utc)
        self.package = RequirementPackageSummary(
            self.package_id, self.project, "Scope", "ACTIVE", self.actor,
            self.now, None, self.now, '"v0"')
        self.requirement = RequirementSummary(
            self.requirement_id, self.project, "REQ-1", "ACTIVE", None,
            self.actor, self.now, None, self.now, '"v0"')
        self.repo = SimpleNamespace(
            list_packages=lambda *_a, **_k: (self.package,),
            get_package=lambda *_a, **_k: RequirementPackageView(
                self.package, (self.requirement_id,)),
            list_requirements=lambda *_a, **_k: (self.requirement,),
            get_requirement=lambda *_a, **_k: self.requirement,
        )
        self.authorization = SimpleNamespace(
            require_in_transaction=lambda *_a, **kwargs: SimpleNamespace(
                user_id=self.actor, project_id=self.project,
                operation=kwargs["operation"]))
        self.query = RequirementIdentityReadQuery(
            b"s" * 32, uuid.uuid4(), self.project)
        self.service = RequirementIdentityReadService(
            unit_of_work=Tx,
            access=SimpleNamespace(
                authenticated_user=lambda *_a, **_k: self.actor),
            license_guard=SimpleNamespace(require_valid=lambda **_k: object()),
            authorization=self.authorization, repository=self.repo,
            clock=lambda: self.now)

    def test_package_page_uses_complete_pair_position(self):
        second = replace(
            self.package, requirement_package_id=uuid.uuid4(),
            updated_at=self.now - timedelta(microseconds=1))
        self.repo.list_packages = lambda *_a, **_k: (self.package, second)
        page = self.service.list_packages(self.query, page_size=1)
        self.assertEqual(page, RequirementPackagePage(
            (self.package,), self.now, self.package_id, True))

    def test_requirement_page_and_details_use_frozen_operations(self):
        page = self.service.list_requirements(self.query, page_size=10)
        self.assertEqual(page, RequirementPage(
            (self.requirement,), None, None, False))
        self.assertEqual(
            self.service.get_requirement(self.query, self.requirement_id),
            self.requirement)
        self.assertEqual(
            self.service.get_package(self.query, self.package_id),
            RequirementPackageView(self.package, (self.requirement_id,)))

    def test_rejects_partial_and_invalid_positions(self):
        for values in (
            {"page_size": 0},
            {"page_size": 201},
            {"page_size": 1, "after_updated_at": self.now},
            {"page_size": 1, "after_requirement_package_id": uuid.uuid4()},
            {"page_size": 1, "after_updated_at": self.now.replace(tzinfo=None),
             "after_requirement_package_id": uuid.uuid4()},
        ):
            with self.subTest(values=values), self.assertRaises(
                    RequirementIdentityReadError) as caught:
                self.service.list_packages(self.query, **values)
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_missing_or_cross_project_detail_is_hidden(self):
        self.repo.get_requirement = lambda *_a, **_k: None
        with self.assertRaises(RequirementIdentityReadError) as caught:
            self.service.get_requirement(self.query, uuid.uuid4())
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")

    def test_repository_shape_and_unsorted_members_fail_closed(self):
        self.repo.list_requirements = lambda *_a, **_k: [self.requirement]
        with self.assertRaises(RequirementIdentityReadError):
            self.service.list_requirements(self.query, page_size=10)
        high, low = sorted((uuid.uuid4(), uuid.uuid4()), key=lambda value: value.bytes,
                           reverse=True)
        self.repo.get_package = lambda *_a, **_k: RequirementPackageView(
            self.package, (high, low))
        with self.assertRaises(RequirementIdentityReadError):
            self.service.get_package(self.query, self.package_id)

    def test_query_redacts_token_and_rejects_invalid_shape(self):
        self.assertNotIn("s" * 32, repr(self.query))
        for values in (
            {"session_token": b"short"},
            {"trace_id": uuid.UUID(int=0)},
            {"project_id": uuid.UUID(int=0)},
        ):
            with self.assertRaises(RequirementIdentityReadError) as caught:
                self.service._validate_query(replace(self.query, **values))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
