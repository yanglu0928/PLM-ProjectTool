from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobRequest
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.parser.application.current_authority import (
    ParserAuthorityError, ParserCurrentAuthority,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectActorFacts, ProjectAuthorizationService,
)


class _ProjectRepo:
    def __init__(self, role="IMPLEMENTATION_MEMBER", state="ACTIVE"):
        self.role, self.state = role, state
        self.locked = None

    def actor_facts(self, tx, *, user_id, project_id, lock=False):
        self.locked = lock
        return ProjectActorFacts(self.state, self.role)


class ParserCurrentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.request = ParseJobRequest(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            1, "PROJECT", uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.user = Mock()
        self.user.current_enabled_user.return_value = CurrentUserFacts(
            self.request.actor_id, "NONE")
        self.project_repo = _ProjectRepo()
        self.projects = ProjectAuthorizationService(unit_of_work=Mock(),
                                                    repository=self.project_repo)
        self.license = Mock()
        self.authority = ParserCurrentAuthority(users=self.user,
            projects=self.projects, license_guard=self.license)

    def test_project_roles_match_upload_and_lock_current_facts(self):
        for role in ("PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"):
            self.project_repo.role = role
            self.authority.assert_current(object(), request=self.request)
            self.assertTrue(self.project_repo.locked)
        self.license.require_valid.assert_called_with(trace_id=self.request.trace_id)
        self.user.current_enabled_user.assert_called_with(
            unittest.mock.ANY, user_id=self.request.actor_id)

    def test_revoked_archived_and_license_denied(self):
        self.user.current_enabled_user.return_value = None
        with self.assertRaises(ParserAuthorityError) as error:
            self.authority.assert_current(object(), request=self.request)
        self.assertEqual(error.exception.code, "AUTH_ACCESS_DENIED")
        self.user.current_enabled_user.return_value = CurrentUserFacts(
            self.request.actor_id, "NONE")
        self.project_repo.role = "CUSTOMER_MEMBER"
        with self.assertRaises(ParserAuthorityError) as error:
            self.authority.assert_current(object(), request=self.request)
        self.assertEqual(error.exception.code, "RESOURCE_NOT_FOUND")
        self.project_repo.role, self.project_repo.state = "PROJECT_MANAGER", "ARCHIVED"
        with self.assertRaises(ParserAuthorityError) as error:
            self.authority.assert_current(object(), request=self.request)
        self.assertEqual(error.exception.code, "PROJECT_ARCHIVED")
        self.project_repo.state = "ACTIVE"
        self.license.require_valid.side_effect = RuntimeLicenseError(
            "LICENSE_OPERATION_DENIED")
        with self.assertRaises(ParserAuthorityError) as error:
            self.authority.assert_current(object(), request=self.request)
        self.assertEqual(error.exception.code, "LICENSE_OPERATION_DENIED")

    def test_global_requires_current_deployment_admin(self):
        global_request = replace(self.request, scope="GLOBAL", project_id=None)
        with self.assertRaises(ParserAuthorityError) as error:
            self.authority.assert_current(object(), request=global_request)
        self.assertEqual(error.exception.code, "AUTH_ACCESS_DENIED")
        self.user.current_enabled_user.return_value = CurrentUserFacts(
            self.request.actor_id, "DEPLOYMENT_ADMIN")
        self.authority.assert_current(object(), request=global_request)
        self.assertIsNone(self.project_repo.locked)


if __name__ == "__main__":
    unittest.main()
