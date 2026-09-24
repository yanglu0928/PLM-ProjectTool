from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.read_projects import ProjectView
from plm_assistant.modules.project.application.write_project import (
    ArchiveProject, PatchProjectName, ProjectWriteError, ProjectWriteService,
)


class Tx:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.state["commits"] += 1


class Access:
    def __init__(self):
        self.user_id = uuid.uuid4()

    def authenticated_user(self, *_args, **_kwargs):
        return self.user_id


class Guard:
    def __init__(self):
        self.calls = 0

    def require_valid(self, **_kwargs):
        self.calls += 1


class Facts:
    def __init__(self):
        self.role = "PROJECT_MANAGER"
        self.project_state = "ACTIVE"
        self.locked = None

    def actor_facts(self, _tx, **kwargs):
        self.locked = kwargs["lock"]
        return None if self.role is None else ProjectActorFacts(self.project_state, self.role)

    def owner_project_id(self, *_args, **_kwargs):
        raise AssertionError("root Project operation has no resource target")


class Repo:
    def __init__(self):
        self.result = ProjectView(uuid.uuid4(), "P1", "New", "ACTIVE",
                                  datetime.now(timezone.utc), '"v1"')
        self.last = None

    def patch_name(self, _tx, **kwargs):
        self.last = ("PATCH", kwargs)
        return self.result

    def archive(self, _tx, **kwargs):
        self.last = ("ARCHIVE", kwargs)
        return self.result


class Audit:
    def __init__(self, state):
        self.state = state

    def append(self, _tx, event):
        self.state["event"] = event


class ProjectWriteTests(unittest.TestCase):
    def setUp(self):
        self.state = {"commits": 0}
        self.access, self.guard, self.facts, self.repo = Access(), Guard(), Facts(), Repo()
        authorization = ProjectAuthorizationService(
            unit_of_work=lambda: Tx(self.state), repository=self.facts,
        )
        self.service = ProjectWriteService(
            unit_of_work=lambda: Tx(self.state), access=self.access,
            license_guard=self.guard, authorization=authorization,
            repository=self.repo, audit=Audit(self.state),
        )
        self.project_id = self.repo.result.project_id
        self.patch = PatchProjectName(b"s" * 32, b"c" * 32, uuid.uuid4(),
                                      self.project_id, 0, " 新名称 ")
        self.archive = ArchiveProject(b"s" * 32, b"c" * 32, uuid.uuid4(),
                                      self.project_id, 0)

    def test_patch_name_audited_and_versioned(self):
        result = self.service.patch_name(self.patch)
        self.assertEqual(result.etag, '"v1"')
        self.assertEqual(self.repo.last[1]["name"], "新名称")
        self.assertTrue(self.facts.locked)
        self.assertEqual(self.state["event"].action, "PROJECT_PATCHED")
        self.assertEqual(self.state["commits"], 1)

    def test_archive_audited(self):
        self.repo.result = ProjectView(self.project_id, "P1", "Name", "ARCHIVED",
                                       datetime.now(timezone.utc), '"v1"')
        result = self.service.archive(self.archive)
        self.assertEqual(result.state, "ARCHIVED")
        self.assertEqual(self.state["event"].action, "PROJECT_ARCHIVED")
        self.assertEqual(self.state["commits"], 1)

    def test_non_manager_or_archived_denied_before_repository(self):
        self.facts.role = "CUSTOMER_MANAGER"
        with self.assertRaises(ProjectWriteError) as caught:
            self.service.patch_name(self.patch)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.facts.role = "PROJECT_MANAGER"
        self.facts.project_state = "ARCHIVED"
        with self.assertRaises(ProjectWriteError) as caught:
            self.service.archive(self.archive)
        self.assertEqual(caught.exception.code, "PROJECT_ARCHIVED")
        self.assertIsNone(self.repo.last)
        self.assertEqual(self.state["commits"], 0)

    def test_invalid_input_rejected_before_guard(self):
        invalid = PatchProjectName(b"s" * 32, b"c" * 32, uuid.uuid4(),
                                   self.project_id, True, "Name")
        with self.assertRaises(ProjectWriteError) as caught:
            self.service.patch_name(invalid)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        with self.assertRaises(ProjectWriteError):
            self.service.patch_name(PatchProjectName(b"s" * 32, b"c" * 32, uuid.uuid4(),
                                                     self.project_id, 0, "\x00"))
        self.assertEqual(self.guard.calls, 0)

    def test_missing_session_denied(self):
        self.access.user_id = None
        with self.assertRaises(ProjectWriteError) as caught:
            self.service.archive(self.archive)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertIsNone(self.repo.last)

    def test_version_conflict_does_not_audit_or_commit(self):
        self.repo.result = None
        with self.assertRaises(ProjectWriteError) as caught:
            self.service.patch_name(self.patch)
        self.assertEqual(caught.exception.code, "CONFLICT_VERSION")
        self.assertNotIn("event", self.state)
        self.assertEqual(self.state["commits"], 0)


if __name__ == "__main__":
    unittest.main()
