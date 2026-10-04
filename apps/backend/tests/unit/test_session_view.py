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
            "password_change_required": False,
            "authorized_projects": [{"project_id": str(project),
                                     "name": "项目甲", "role": "PROJECT_MANAGER"}],
        })

    def test_restricted_never_projects_admin(self):
        view=LoginSessionView(uuid.uuid4(),'Synthetic restricted','DEPLOYMENT_ADMIN',(
            AuthorizedProjectSummary(uuid.uuid4(),'Must not disclose','PROJECT_MANAGER'),),True)
        data=view.public_data()
        self.assertEqual(data['deployment_role'],'NONE')
        self.assertEqual(data['authorized_projects'],[])
        self.assertIs(data['password_change_required'],True)

    def test_password_flag_not_truthiness(self):
        with self.assertRaises(ValueError):LoginSessionView(uuid.uuid4(),'Synthetic','NONE',(),1).public_data()


if __name__ == "__main__":
    unittest.main()
