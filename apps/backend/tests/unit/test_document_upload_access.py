"""Frozen upload role matrix and live request identity boundary."""

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.document.application.upload_access import (
    DocumentUploadAccess, DocumentUploadAccessError,
)


class _Session:
    user = None

    def authenticated_user(self, transaction, **kwargs):
        return self.user


class _Admin:
    user = None

    def authorized_admin(self, transaction, **kwargs):
        return self.user


class _Facts:
    role = "PROJECT_MANAGER"
    state = "ACTIVE"

    def actor_facts(self, transaction, **kwargs):
        return SimpleNamespace(project_role=self.role, project_state=self.state) if self.role else None


class _Owner:
    user = None

    def creator_id(self, transaction, **kwargs):
        return self.user


class DocumentUploadAccessTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.upload = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.session, self.admin, self.facts, self.owner = _Session(), _Admin(), _Facts(), _Owner()
        self.session.user = self.admin.user = self.owner.user = self.actor
        self.access = DocumentUploadAccess(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            session_access=self.session, admin_access=self.admin,
            project_facts=self.facts, upload_owner=self.owner,
            clock=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc),
        )

    def _require(self, *, content=False, global_scope=False):
        self.access.require_in_transaction(
            object(), actor_id=self.actor,
            scope="GLOBAL" if global_scope else "PROJECT",
            project_id=None if global_scope else self.project,
            operation="V1_DOCUMENT_UPLOAD_CONTENT" if content else "V1_DOCUMENT_UPLOAD_CREATE",
            **({"upload_id": self.upload} if content else {"target_document_id": None}),
        )

    def test_project_create_role_matrix(self):
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"):
            self.facts.role = role
            self._require()
        for role in ("CUSTOMER_MEMBER", None):
            self.facts.role = role
            with self.assertRaises(DocumentUploadAccessError) as result:
                self._require()
            self.assertEqual(result.exception.code, "RESOURCE_NOT_FOUND")

    def test_revoked_or_spoofed_session_denied(self):
        self.session.user = None
        with self.assertRaises(DocumentUploadAccessError) as result:
            self._require()
        self.assertEqual(result.exception.code, "AUTH_ACCESS_DENIED")
        self.session.user = uuid.uuid4()
        with self.assertRaises(DocumentUploadAccessError):
            self._require()

    def test_archived_project_denied(self):
        self.facts.state = "ARCHIVED"
        with self.assertRaises(DocumentUploadAccessError) as result:
            self._require()
        self.assertEqual(result.exception.code, "PROJECT_ARCHIVED")

    def test_content_requires_creator_even_with_upload_role(self):
        self._require(content=True)
        self.owner.user = uuid.uuid4()
        with self.assertRaises(DocumentUploadAccessError) as result:
            self._require(content=True)
        self.assertEqual(result.exception.code, "RESOURCE_NOT_FOUND")

    def test_global_requires_deployment_admin(self):
        self._require(global_scope=True)
        self.admin.user = None
        with self.assertRaises(DocumentUploadAccessError) as result:
            self._require(global_scope=True)
        self.assertEqual(result.exception.code, "AUTH_ACCESS_DENIED")

    def test_scope_and_operation_cannot_be_relaxed(self):
        with self.assertRaises(DocumentUploadAccessError):
            self.access.require_in_transaction(
                object(), actor_id=self.actor, scope="PROJECT", project_id=None,
                operation="V1_DOCUMENT_UPLOAD_CREATE",
            )
        with self.assertRaises(DocumentUploadAccessError):
            self.access.require_in_transaction(
                object(), actor_id=self.actor, scope="GLOBAL", project_id=None,
                operation="V1_DOCUMENT_UPLOAD_ABORT",
            )


if __name__ == "__main__":
    unittest.main()
