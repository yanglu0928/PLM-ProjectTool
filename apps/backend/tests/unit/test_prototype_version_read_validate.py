from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView, VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeVersionQuery, PrototypeVersionReadError,
    PrototypeVersionReadValidationService,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class Tx:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def commit(self): self.committed = True


class Access:
    actor = uuid.uuid4()
    def authenticated_user(self, *_args, **_kwargs): return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        return SimpleNamespace(user_id=user_id, project_id=project_id, operation=operation)


class Audit:
    def append(self, *_args, **_kwargs): self.called = True


class Proof:
    def __init__(self): self.available = True
    def prove(self, *_args, **_kwargs): return object() if self.available else None
    def prove_for_prototype_version(self, *_args, **_kwargs):
        return object() if self.available else None


class Repo:
    def __init__(self, views): self.views = views
    def list(self, _tx, *, before_version_no, limit, **_kwargs):
        rows = [x for x in self.views if before_version_no is None
                or x.version_no < before_version_no]
        return tuple(rows[:limit])
    def get(self, _tx, *, version_id, **_kwargs):
        return next((x for x in self.views if x.prototype_version_id == version_id), None)


class PrototypeVersionReadValidateTests(unittest.TestCase):
    def setUp(self):
        self.project, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.template, self.template_version = uuid.uuid4(), uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.document = uuid.uuid4()
        self.views = tuple(self.view(no) for no in (3, 2, 1))
        self.templates, self.requirements, self.documents = Proof(), Proof(), Proof()
        self.audit = Audit()
        self.service = PrototypeVersionReadValidationService(
            unit_of_work=Tx, project_access=Access(), license_guard=Guard(),
            authorization=Authorization(), repository=Repo(self.views),
            templates=self.templates, requirements=self.requirements,
            documents=self.documents, audit=self.audit, clock=lambda: NOW)
        self.query = PrototypeVersionQuery(
            b"s" * 32, uuid.uuid4(), self.project, self.prototype)

    def view(self, number):
        return PrototypeVersionInitialView(
            uuid.uuid4(), self.prototype, self.project, number, None,
            self.template, self.template_version,
            (VersionArtifactRef("DOCUMENT_VERSION", self.document),),
            (VersionRequirementRef(self.requirement, self.requirement_version),),
            {"interactions": []}, {"covered": 1}, "1" * 64, NOW)

    def test_list_uses_descending_version_cursor(self):
        page = self.service.list(self.query, page_size=2)
        self.assertEqual([x.version_no for x in page.items], [3, 2])
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_version_no, 2)
        second = self.service.list(
            self.query, page_size=2, before_version_no=page.next_version_no)
        self.assertEqual([x.version_no for x in second.items], [1])

    def test_get_is_scoped_and_missing_is_not_found(self):
        self.assertEqual(self.service.get(
            self.query, version_id=self.views[0].prototype_version_id), self.views[0])
        with self.assertRaisesRegex(PrototypeVersionReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(self.query, version_id=uuid.uuid4())

    def test_validate_reports_current_proof_health_without_state_change(self):
        report = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32)
        self.assertTrue(report.valid)
        self.assertEqual(report.issues, ())
        self.assertEqual(report.version_state, "DRAFT")
        self.documents.available = False
        failed = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32)
        self.assertFalse(failed.valid)
        self.assertEqual(failed.issues, ("ARTIFACT_UNAVAILABLE",))
        self.assertEqual(failed.version_state, "DRAFT")

    def test_validate_rejects_missing_csrf(self):
        with self.assertRaisesRegex(PrototypeVersionReadError, "VALIDATION_FAILED"):
            self.service.validate(
                self.query, version_id=self.views[0].prototype_version_id,
                csrf_token=b"bad")


if __name__ == "__main__": unittest.main()
