"""GLOBAL candidate Owner authorization and independent cursor family."""

from __future__ import annotations

import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec, GlobalReferenceCandidateCursorError,
)
from plm_assistant.modules.solution.application.list_global_reference_candidates import (
    GlobalReferenceCandidate, GlobalReferenceCandidatePage,
)
from plm_assistant.modules.solution.application.read_global_reference_candidates import (
    GlobalReferenceCandidateReadError, GlobalReferenceCandidateReadQuery,
    GlobalReferenceCandidateReadService,
)


USER = uuid.UUID("00000000-0000-0000-0000-000000000011")
PROJECT = uuid.UUID("00000000-0000-0000-0000-000000000012")
ROOT = uuid.UUID("00000000-0000-0000-0000-000000000013")
VERSION = uuid.UUID("00000000-0000-0000-0000-000000000014")
TRACE = uuid.UUID("00000000-0000-0000-0000-000000000015")
TOKEN = b"s" * 32
ITEM = GlobalReferenceCandidate(ROOT, VERSION, "审定标签", 1, "ELIGIBLE")


class Runtime:
    @contextmanager
    def unit_of_work(self):
        yield self


class Access:
    def __init__(self, user=USER):
        self.user = user
        self.calls = 0

    def authenticated_user(self, _tx, *, session_token, now):
        self.calls += 1
        assert session_token == TOKEN and now.tzinfo is not None
        return self.user


class License:
    def require_valid(self, *, trace_id):
        assert trace_id == TRACE
        return object()


class ProjectRepository:
    def __init__(self, role="PROJECT_MANAGER", state="ACTIVE"):
        self.role, self.state = role, state

    def actor_facts(self, _tx, *, user_id, project_id, lock=False):
        assert user_id == USER and project_id == PROJECT and lock is True
        return (ProjectActorFacts(self.state, self.role)
                if self.role is not None else None)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("candidate list has no target resource")


class Catalog:
    def __init__(self):
        self.calls = []

    def scan(self, _tx, *, trace_id, project_id,
             after_reference_solution_id, limit):
        self.calls.append((trace_id, project_id,
                           after_reference_solution_id, limit))
        return GlobalReferenceCandidatePage((ITEM,), ROOT, True)


def service(*, role="PROJECT_MANAGER", state="ACTIVE", user=USER,
            license_guard=None):
    runtime, access, catalog = Runtime(), Access(user), Catalog()
    reader = GlobalReferenceCandidateReadService(
        unit_of_work=runtime.unit_of_work, access=access,
        license_guard=license_guard or License(),
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=ProjectRepository(role, state)),
        catalog=catalog,
        cursor=GlobalReferenceCandidateCursorCodec(b"k" * 32),
        clock=lambda: datetime.now(timezone.utc))
    return reader, access, catalog


class GlobalReferenceCandidateReadTests(unittest.TestCase):
    def test_project_writer_roles_and_raw_cursor(self):
        query = GlobalReferenceCandidateReadQuery(TOKEN, TRACE, PROJECT)
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"):
            with self.subTest(role=role):
                reader, _, catalog = service(role=role)
                page = reader.list(query, page_size=1)
                self.assertEqual(page.items, (ITEM,))
                self.assertTrue(page.has_more)
                self.assertIsNotNone(page.next_cursor)
                reader.list(query, page_size=1, cursor=page.next_cursor)
                self.assertEqual(catalog.calls[-1], (TRACE, PROJECT, ROOT, 1))

    def test_customer_suspended_archived_and_missing_session_never_scan(self):
        query = GlobalReferenceCandidateReadQuery(TOKEN, TRACE, PROJECT)
        for role, state, user in (
                ("CUSTOMER_MANAGER", "ACTIVE", USER),
                ("CUSTOMER_MEMBER", "ACTIVE", USER),
                (None, "ACTIVE", USER),
                ("PROJECT_MANAGER", "ARCHIVED", USER),
                ("PROJECT_MANAGER", "ACTIVE", None)):
            with self.subTest(role=role, state=state, user=user):
                reader, _, catalog = service(role=role, state=state, user=user)
                with self.assertRaises(GlobalReferenceCandidateReadError):
                    reader.list(query)
                self.assertEqual(catalog.calls, [])

    def test_cursor_scope_and_tamper_rejected_before_catalog(self):
        query = GlobalReferenceCandidateReadQuery(TOKEN, TRACE, PROJECT)
        reader, _, catalog = service()
        token = reader.list(query, page_size=1).next_cursor
        self.assertIsNotNone(token)
        good_calls = len(catalog.calls)
        for changed in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                        token + "A"):
            with self.subTest(changed=changed[-8:]):
                with self.assertRaises(GlobalReferenceCandidateReadError):
                    reader.list(query, page_size=1, cursor=changed)
        with self.assertRaises(GlobalReferenceCandidateCursorError):
            GlobalReferenceCandidateCursorCodec(b"k" * 32).decode(
                token, session_token=b"x" * 32,
                project_id=PROJECT, page_size=1)
        with self.assertRaises(GlobalReferenceCandidateCursorError):
            GlobalReferenceCandidateCursorCodec(b"k" * 32).decode(
                token, session_token=TOKEN,
                project_id=uuid.uuid4(), page_size=1)
        with self.assertRaises(GlobalReferenceCandidateCursorError):
            GlobalReferenceCandidateCursorCodec(b"k" * 32).decode(
                token, session_token=TOKEN,
                project_id=PROJECT, page_size=2)
        self.assertEqual(len(catalog.calls), good_calls)

    def test_expired_license_never_enters_catalog(self):
        class DeniedLicense:
            def require_valid(self, *, trace_id):
                raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")

        reader, access, catalog = service(license_guard=DeniedLicense())
        with self.assertRaises(GlobalReferenceCandidateReadError) as caught:
            reader.list(GlobalReferenceCandidateReadQuery(TOKEN, TRACE, PROJECT))
        self.assertEqual(caught.exception.code, "LICENSE_OPERATION_DENIED")
        self.assertEqual(access.calls, 0)
        self.assertEqual(catalog.calls, [])


if __name__ == "__main__":
    unittest.main()
