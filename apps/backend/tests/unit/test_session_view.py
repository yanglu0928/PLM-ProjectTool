from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.auth.application.session_view import (
    AuthorizedProjectSummary, LoginSessionView,
)


class SessionViewTests(unittest.TestCase):
    def test_public_fields_are_explicit(self):
        user, project = uuid.uuid4(), uuid.uuid4()
        view = LoginSessionView(user, "测试用户", "NONE", (
            AuthorizedProjectSummary(project, "项目甲", "PROJECT_MANAGER"),
        ))
        self.assertEqual(view.public_data(), {
            "user": {"user_id": str(user), "username_display": "测试用户"},
            "deployment_role": "NONE",
            "authorized_projects": [{"project_id": str(project),
                                     "name": "项目甲", "role": "PROJECT_MANAGER"}],
        })


if __name__ == "__main__":
    unittest.main()
