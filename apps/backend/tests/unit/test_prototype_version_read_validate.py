from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView, VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeValidationAudit,
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
    def authenticated_user(self, *_args, session_token, now): return self.actor


class WriteAccess:
    actor = Access.actor
    def authenticated_user(self, *_args, session_token, csrf_token, now):
        return self.actor


class Guard:
    def require_valid(self, **_kwargs): return object()


class Authorization:
    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        return SimpleNamespace(user_id=user_id, project_id=project_id, operation=operation)


class AuditSource:
    def __init__(self): self.values = {}
    def get(self, _tx, *, audit_event_id, **_kwargs):
        return self.values.get(audit_event_id)


class Audit:
    def __init__(self, source): self.source = source; self.calls = 0
    def append(self, _tx, draft):
        self.calls += 1
        identity = uuid.uuid4()
        self.source.values[identity] = PrototypeValidationAudit(
            identity, draft.trace_id, NOW, draft.reason_code,
            draft.before_state,
        )
        return identity


class Receipts:
    def __init__(self): self.values = {}
    def reserve(self, _tx, *, scope, request_fingerprint):
        found = self.values.get(scope.key_digest)
        if found is None:
            self.pending = (scope.key_digest, request_fingerprint)
            return None
        fingerprint, result = found
        if fingerprint != request_fingerprint:
            from plm_assistant.modules.platform.application.idempotency import IdempotencyError
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return result
    def complete(self, _tx, *, scope, result):
        self.values[scope.key_digest] = (self.pending[1], result)


class Proof:
    def __init__(self): self.available = True
    def prove(self, *_args, **_kwargs): return object() if self.available else None
    def prove_for_prototype_version(self, *_args, **_kwargs):
        if not self.available:
            return None
        return SimpleNamespace(
            document_version_id=_kwargs["document_version_id"],
            document_id=uuid.uuid5(uuid.NAMESPACE_URL, "prototype-document-root"),
            scope="PROJECT", project_id=_kwargs["project_id"],
        )


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
        self.audit_source, self.receipts = AuditSource(), Receipts()
        self.audit = Audit(self.audit_source)
        self.service = PrototypeVersionReadValidationService(
            unit_of_work=Tx, project_access=Access(), write_access=WriteAccess(),
            license_guard=Guard(),
            authorization=Authorization(), repository=Repo(self.views),
            templates=self.templates, requirements=self.requirements,
            documents=self.documents, audit_source=self.audit_source,
            receipts=self.receipts, audit=self.audit, clock=lambda: NOW)
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
        self.assertEqual(
            page.items[0].artifact_refs[0].document_id,
            uuid.uuid5(uuid.NAMESPACE_URL, "prototype-document-root"),
        )
        self.assertTrue(page.has_more)
        self.assertEqual(page.next_version_no, 2)
        second = self.service.list(
            self.query, page_size=2, before_version_no=page.next_version_no)
        self.assertEqual([x.version_no for x in second.items], [1])

    def test_get_is_scoped_and_missing_is_not_found(self):
        result = self.service.get(
            self.query, version_id=self.views[0].prototype_version_id)
        self.assertEqual(result.prototype_version_id,
                         self.views[0].prototype_version_id)
        self.assertEqual(result.artifact_refs[0].target_id, self.document)
        self.assertIsNotNone(result.artifact_refs[0].document_id)
        with self.assertRaisesRegex(PrototypeVersionReadError, "RESOURCE_NOT_FOUND"):
            self.service.get(self.query, version_id=uuid.uuid4())

    def test_validate_reports_current_proof_health_without_state_change(self):
        report = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32, idempotency_key="validation-key-123")
        self.assertTrue(report.valid)
        self.assertEqual(report.issues, ())
        self.assertEqual(report.version_state, "DRAFT")
        self.documents.available = False
        replay = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32, idempotency_key="validation-key-123")
        self.assertTrue(replay.valid)
        self.assertEqual(report.audit_event_id, replay.audit_event_id)
        self.assertEqual(1, self.audit.calls)
        failed = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32, idempotency_key="validation-key-456")
        self.assertFalse(failed.valid)
        self.assertEqual(failed.issues, ("ARTIFACT_UNAVAILABLE",))
        self.assertEqual(failed.version_state, "DRAFT")
        self.assertEqual(2, self.audit.calls)

    def test_validate_rejects_missing_csrf(self):
        with self.assertRaisesRegex(PrototypeVersionReadError, "VALIDATION_FAILED"):
            self.service.validate(
                self.query, version_id=self.views[0].prototype_version_id,
                csrf_token=b"bad", idempotency_key="validation-key-123")

    def test_validate_key_is_bound_to_version_and_replay_proof(self):
        key = "validation-bound-key"
        first = self.service.validate(
            self.query, version_id=self.views[0].prototype_version_id,
            csrf_token=b"c" * 32, idempotency_key=key)
        with self.assertRaisesRegex(PrototypeVersionReadError,
                                    "CONFLICT_IDEMPOTENCY"):
            self.service.validate(
                self.query, version_id=self.views[1].prototype_version_id,
                csrf_token=b"c" * 32, idempotency_key=key)
        self.audit_source.values[first.audit_event_id] = PrototypeValidationAudit(
            first.audit_event_id, self.query.trace_id, NOW,
            "PRT_VALIDATION_FAILED_X", "DRAFT",
        )
        with self.assertRaisesRegex(PrototypeVersionReadError,
                                    "PROTOTYPE_UNAVAILABLE"):
            self.service.validate(
                self.query, version_id=self.views[0].prototype_version_id,
                csrf_token=b"c" * 32, idempotency_key=key)


if __name__ == "__main__": unittest.main()
