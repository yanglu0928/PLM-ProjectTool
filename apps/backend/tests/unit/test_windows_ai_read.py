from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock

from plm_assistant.entrypoints.windows_ai_read import (
    WindowsAIReadStartupError,
    create_windows_ai_read_routers,
)
from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


class Documents:
    def get_version(self, *_args, **_kwargs): raise AssertionError("not called")


class Results:
    def read(self, *_args, **_kwargs): raise AssertionError("not called")


class WindowsAIReadCompositionTests(TestCase):
    def setUp(self) -> None:
        self.runtime = Mock()
        self.runtime.unit_of_work = Mock()
        self.kwargs = {
            "runtime": self.runtime,
            "origins": LoginOriginPolicy(["https://plm.example.test"]),
            "license_guard": Mock(),
            "task_cursors": AITaskListCursorCodec(b"r" * 32),
            "invocation_cursors": AIInvocationListCursorCodec(b"r" * 32),
            "documents": Documents(), "parse_results": Results(),
        }

    def test_builds_all_three_routes_only_with_document_owners(self):
        routers = create_windows_ai_read_routers(**self.kwargs)
        paths = {
            route.path for router in (
                routers.tasks, routers.invocations, routers.suggestion,
            ) for route in router.routes
        }
        self.assertEqual(paths, {
            "/api/v1/projects/{project_id}/ai-tasks",
            "/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/invocations",
            "/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/suggestion",
        })

    def test_missing_locator_owner_or_wrong_codec_fails_closed(self):
        for name, value in (
            ("documents", object()), ("parse_results", object()),
            ("task_cursors", object()), ("invocation_cursors", object()),
        ):
            with self.subTest(name=name), self.assertRaises(WindowsAIReadStartupError):
                create_windows_ai_read_routers(**(self.kwargs | {name: value}))


if __name__ == "__main__":
    import unittest
    unittest.main()
