from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecHistoryView, StructuredSpecReadError,
    StructuredSpecReadQuery, StructuredSpecReadService,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef,
)


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Access:
    actor: uuid.UUID | None = None

    def authenticated_user(self, _tx, *, session_token, now):
        assert len(session_token) == 32 and now.tzinfo is not None
        return self.actor


class _Guard:
    valid = True

    def require_valid(self, *, trace_id):
        assert trace_id.int != 0
        if not self.valid:
            raise RuntimeLicenseError("LICENSE_EXPIRED")


class _Authorization:
    denied = False

    def require_in_transaction(self, _tx, *, user_id, project_id, operation):
        assert operation == "SOL_STRUCTURED_SPEC_GET"
        if self.denied:
            return SimpleNamespace(user_id=user_id, project_id=uuid.uuid4(),
                                   operation=operation)
        return SimpleNamespace(user_id=user_id, project_id=project_id,
                               operation=operation)


class _Specs:
    view = None

    def get(self, _tx, *, project_id, spec_id):
        if (self.view and self.view.project_id == project_id
                and self.view.structured_solution_spec_id == spec_id):
            return self.view
        return None


class StructuredSpecReadTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.spec = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.view = StructuredSpecHistoryView(
            self.spec, uuid.uuid4(), self.project, "MIGRATION_SPEC", 1,
            "DRAFT", b"c" * 32, b'{"scope":"Parts"}', b"p" * 32,
            (SpecRequirementRef(uuid.uuid4(), uuid.uuid4()),),
            (SpecSectionRef(uuid.uuid4(), uuid.uuid4()),),
            (uuid.uuid4(),), (), None, None, None, self.actor,
            datetime.now(timezone.utc))
        self.access, self.guard = _Access(), _Guard()
        self.access.actor = self.actor
        self.authorization, self.specs = _Authorization(), _Specs()
        self.specs.view = self.view
        self.service = StructuredSpecReadService(
            unit_of_work=_Tx, access=self.access, license_guard=self.guard,
            authorization=self.authorization, specs=self.specs)
        self.query = StructuredSpecReadQuery(b"s" * 32, uuid.uuid4(), self.project)

    def test_reads_fixed_detail_and_rejects_cross_project(self):
        self.assertEqual(self.service.get(self.query, self.spec), self.view)
        with self.assertRaises(StructuredSpecReadError) as failure:
            self.service.get(replace(self.query, project_id=uuid.uuid4()), self.spec)
        self.assertEqual(failure.exception.code, "RESOURCE_NOT_FOUND")

    def test_denied_or_missing_session_or_license_fails_closed(self):
        self.authorization.denied = True
        with self.assertRaises(StructuredSpecReadError) as failure:
            self.service.get(self.query, self.spec)
        self.assertEqual(failure.exception.code, "RESOURCE_NOT_FOUND")
        self.authorization.denied = False
        self.access.actor = None
        with self.assertRaises(StructuredSpecReadError) as failure:
            self.service.get(self.query, self.spec)
        self.assertEqual(failure.exception.code, "AUTH_ACCESS_DENIED")
        self.access.actor = self.actor
        self.guard.valid = False
        with self.assertRaises(StructuredSpecReadError) as failure:
            self.service.get(self.query, self.spec)
        self.assertEqual(failure.exception.code, "LICENSE_OPERATION_DENIED")

    def test_inconsistent_history_or_query_fails_closed(self):
        for broken in (
                replace(self.view, version_no=2),
                replace(self.view, payload_fingerprint=b"bad"),
                replace(self.view, project_id=uuid.uuid4()),
                replace(self.view, artifact_ids=(uuid.uuid4(),))):
            self.specs.view = broken
            with self.assertRaises(StructuredSpecReadError):
                self.service.get(self.query, self.spec)
        self.specs.view = self.view
        with self.assertRaises(StructuredSpecReadError) as failure:
            self.service.get(replace(self.query, session_token=b"bad"), self.spec)
        self.assertEqual(failure.exception.code, "VALIDATION_FAILED")
