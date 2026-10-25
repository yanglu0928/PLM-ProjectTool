from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.member_candidates import create_project_member_candidate_router
from plm_assistant.modules.project.application.member_candidates import (
    MemberCandidateView, ProjectMemberCandidateError,
)


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Candidates:
    def __init__(self):
        self.calls = 0
        self.fail = None
        self.result = MemberCandidateView(uuid.uuid4(), "Target User")

    def exact(self, query):
        self.calls += 1
        assert query.username == "Target"
        if self.fail == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.fail:
            raise ProjectMemberCandidateError(self.fail)
        return self.result


class CandidateApiTests(unittest.TestCase):
    def setUp(self):
        self.candidates = Candidates()
        self.project_id = uuid.uuid4()
        router = create_project_member_candidate_router(
            sessions=Sessions(), candidates=self.candidates,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(project_member_candidate_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/member-candidates:resolve"
        self.headers = {"cookie": "plm_session=" + (b"a" * 32).hex(),
                        "origin": "https://plm.example.test", "x-csrf-token": (b"c" * 32).hex()}

    def resolve(self, path=None, *, headers=None, body=None):
        return self.client.post(path or self.path, headers=self.headers if headers is None else headers,
                                json={"username": "Target"} if body is None else body)

    def test_default_closed_and_minimal_hit_or_uniform_miss(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.resolve()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.json()["data"], {"candidate": {
            "user_id": str(self.candidates.result.user_id), "display_name": "Target User",
        }})
        self.candidates.result = None
        self.assertEqual(self.resolve().json()["data"], {"candidate": None})

    def test_session_origin_scope_and_query_fail_closed(self):
        self.assertEqual(self.resolve(headers={}).status_code, 403)
        for dropped, status in (("cookie", 401), ("origin", 403), ("x-csrf-token", 403)):
            self.assertEqual(self.resolve(headers={k: v for k, v in self.headers.items() if k != dropped}).status_code, status)
        self.assertEqual(self.resolve(headers={**self.headers, "host": "other.example"}).status_code, 403)
        for path, status in (
            (self.path + "?username=Target", 400),
            (self.path.replace(str(self.project_id), str(uuid.UUID(int=0))), 404),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.resolve(path).status_code, status)
        for body, status in (({}, 400), ({"username": "Target", "extra": "x"}, 400),
                             ({"username": ""}, 422), ({"username": "x" * 256}, 422)):
            with self.subTest(body=body):
                self.assertEqual(self.resolve(body=body).status_code, status)
        self.assertEqual(self.candidates.calls, 0)

    def test_permission_license_rate_and_errors_do_not_leak(self):
        for code, status in (("RESOURCE_NOT_FOUND", 404), ("PROJECT_ARCHIVED", 409),
                             ("AUTH_RATE_LIMITED", 429), ("LICENSE", 403),
                             ("PROJECT_UNAVAILABLE", 503)):
            self.candidates.fail = code
            with self.subTest(code=code):
                response = self.resolve()
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)
                self.assertNotIn("Target User", response.text)


if __name__ == "__main__":
    unittest.main()
