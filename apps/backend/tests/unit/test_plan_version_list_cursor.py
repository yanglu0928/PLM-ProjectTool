from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec


class PlanVersionListCursorTests(unittest.TestCase):
    def test_cursor_is_domain_session_scope_and_query_bound(self):
        codec = PlanVersionListCursorCodec(b"k" * 32)
        project, plan = uuid.uuid4(), uuid.uuid4()
        token = codec.encode(session_token=b"s" * 32, project_id=project,
                             plan_id=plan, page_size=25, version_no=7)
        self.assertEqual(codec.decode(token, session_token=b"s" * 32,
                                      project_id=project, plan_id=plan,
                                      page_size=25), 7)
        for kwargs in (
            {"session_token": b"x" * 32, "project_id": project,
             "plan_id": plan, "page_size": 25},
            {"session_token": b"s" * 32, "project_id": uuid.uuid4(),
             "plan_id": plan, "page_size": 25},
            {"session_token": b"s" * 32, "project_id": project,
             "plan_id": uuid.uuid4(), "page_size": 25},
            {"session_token": b"s" * 32, "project_id": project,
             "plan_id": plan, "page_size": 26},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ApplicationError):
                codec.decode(token, **kwargs)

    def test_tampered_and_malformed_cursors_fail_closed(self):
        codec = PlanVersionListCursorCodec(b"k" * 32)
        project, plan = uuid.uuid4(), uuid.uuid4()
        token = codec.encode(session_token=b"s" * 32, project_id=project,
                             plan_id=plan, page_size=1, version_no=2)
        for invalid in (token[:-1] + ("A" if token[-1] != "A" else "B"), "@@@@.###"):
            with self.subTest(invalid=invalid), self.assertRaises(ApplicationError):
                codec.decode(invalid, session_token=b"s" * 32, project_id=project,
                             plan_id=plan, page_size=1)
