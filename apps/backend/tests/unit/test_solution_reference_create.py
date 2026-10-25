from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateError, ReferenceCreateService,
    ReferenceInitialView,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    QualifiedReferenceSources, ReferenceSourceRequest, VerifiedReferenceDocument,
)


NOW = datetime(2026, 10, 8, 16, tzinfo=timezone.utc)
ACTOR, DOC, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.committed = True


class Uow:
    def __init__(self):
        self.items = []

    def __call__(self):
        tx = Tx()
        self.items.append(tx)
        return tx


class Access:
    def __init__(self):
        self.actor = ACTOR

    def authorized_admin(self, tx, **kwargs):
        return self.actor

    def authenticated_user(self, tx, **kwargs):
        return self.actor


class ProjectRepo:
    def __init__(self):
        self.role, self.state = "PROJECT_MANAGER", "ACTIVE"

    def actor_facts(self, tx, **kwargs):
        return ProjectActorFacts(self.state, self.role)

    def owner_project_id(self, tx, **kwargs):
        return None


class License:
    def require_valid(self, *, trace_id):
        return object()


class Sources:
    def __init__(self, scope, project):
        self.result = QualifiedReferenceSources(
            scope, project, (VerifiedReferenceDocument(
                DOC, VERSION, scope, project, "REFERENCE_MATERIAL", b"d" * 32),),
            (), b"s" * 32,
            uuid.uuid4() if scope == "GLOBAL" else None,
        )

    def qualify(self, tx, request):
        return self.result


class Repository:
    def __init__(self):
        self.created = []
        self.result = None

    def create(self, tx, **kwargs):
        self.created.append((tx, kwargs))
        self.result = ReferenceInitialView(
            kwargs["root_id"], kwargs["version_id"], kwargs["sources"].scope,
            kwargs["sources"].project_id, kwargs["name"],
            kwargs["qualified"].content_fingerprint,
            kwargs["content_fingerprint"],
            kwargs["qualified"].deidentification_confirmation_id,
            kwargs["actor_id"], NOW,
        )
        return self.result

    def view(self, tx, *, root_id, scope, project_id):
        return self.result if self.result and self.result.reference_solution_id == root_id else None


class Receipts:
    def __init__(self):
        self.record = None

    def reserve(self, tx, *, scope, request_fingerprint):
        if self.record is None:
            self.record = (scope, request_fingerprint, None)
            return None
        if self.record[1] != request_fingerprint:
            raise IdempotencyError("CONFLICT_IDEMPOTENCY")
        return self.record[2]

    def complete(self, tx, *, scope, result):
        self.record = (scope, self.record[1], result)


class Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, event):
        self.events.append((tx, event))
        if self.fail:
            raise RuntimeError("synthetic audit failure")


class ReferenceCreateTests(unittest.TestCase):
    def setUp(self):
        self.uow, self.access, self.projects = Uow(), Access(), ProjectRepo()
        self.sources, self.repo, self.receipts, self.audit = (
            Sources("GLOBAL", None), Repository(), Receipts(), Audit())
        self.service = ReferenceCreateService(
            unit_of_work=self.uow, global_access=self.access,
            project_access=self.access,
            project_authorization=ProjectAuthorizationService(
                unit_of_work=self.uow, repository=self.projects),
            license_guard=License(), sources=self.sources,
            repository=self.repo, receipts=self.receipts,
            audit=self.audit, clock=lambda: NOW,
        )
        self.command = CreateReferenceSolution(
            ReferenceSourceRequest(b"s" * 32, uuid.uuid4(), "GLOBAL", None,
                                   (VERSION,), (), "PLM", "DEIDENTIFIED", {}),
            b"c" * 32, "Reference", "i" * 16,
        )

    def test_global_initial_write_audit_and_replay(self):
        first = self.service.create(self.command)
        again = self.service.create(replace(
            self.command, sources=replace(self.command.sources, trace_id=uuid.uuid4())))
        self.assertEqual(first, again)
        self.assertEqual(len(self.repo.created), 1)
        self.assertEqual(len(self.audit.events), 1)
        self.assertIs(self.audit.events[0][0], self.repo.created[0][0])
        self.assertTrue(self.uow.items[1].committed)
        self.assertNotIn((b"s" * 32).hex(), repr(first))
        with self.assertRaisesRegex(ReferenceCreateError, "CONFLICT_IDEMPOTENCY"):
            self.service.create(replace(self.command, name="Changed"))

    def test_project_role_and_archived_denial(self):
        project = uuid.uuid4()
        self.sources = Sources("PROJECT", project)
        self.service._sources = self.sources
        command = replace(self.command, sources=replace(
            self.command.sources, scope="PROJECT", project_id=project))
        self.projects.role = "IMPLEMENTATION_MEMBER"
        self.assertEqual(self.service.create(command).project_id, project)
        for role, state in (("CUSTOMER_MANAGER", "ACTIVE"),
                            ("PROJECT_MANAGER", "ARCHIVED")):
            self.projects.role, self.projects.state = role, state
            with self.subTest(role=role, state=state):
                with self.assertRaises(ReferenceCreateError):
                    self.service.create(command)

    def test_admin_denial_and_audit_failure_never_commit(self):
        self.access.actor = None
        with self.assertRaisesRegex(ReferenceCreateError, "AUTH_ACCESS_DENIED"):
            self.service.create(self.command)
        self.access.actor = ACTOR
        self.audit.fail = True
        with self.assertRaisesRegex(ReferenceCreateError, "SOLUTION_UNAVAILABLE"):
            self.service.create(self.command)
        self.assertFalse(self.uow.items[-1].committed)


if __name__ == "__main__":
    unittest.main()
