from __future__ import annotations

import unittest
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.task_submission_options import (
    create_ai_task_submission_options_router,
)
from plm_assistant.modules.ai.application.egress_preview import EgressPreviewPolicy
from plm_assistant.modules.ai.application.task_submission_options import (
    AITaskRouteCandidate, AITaskSubmissionOptionsError, AITaskSubmissionOptionsView,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskSubmissionPolicy,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


class Options:
    failure = None
    query = None

    def __init__(self, view):
        self.view = view

    def get(self, query):
        self.query = query
        if self.failure:
            raise AITaskSubmissionOptionsError(self.failure)
        return self.view


class AITaskSubmissionOptionsApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.provider, self.model = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.view = AITaskSubmissionOptionsView(
            (AITaskSubmissionPolicy(
                "gap-analysis.v1", 1, "GAP_ANALYSIS", uuid.uuid4(),
                "project-gap-analysis.v1", "gap-output.v2", "no-retrieval.v1",
                (AITaskParameterField("language", "STRING", True, 16,
                                      allowed_values=("zh-CN",)),),
            ),),
            (EgressPreviewPolicy(
                "minimal-document-text.v1", frozenset({"AI_TASK"}),
                frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30), 50,
                1_048_576, 32_768, 2, ("EXTERNAL_PROCESSING",),
            ),),
            (AITaskRouteCandidate(
                self.provider, self.model, "合成服务", "cn-beijing",
                ProviderKind.OPENAI_COMPATIBLE, "endpoint.business.v1",
                "EXTERNAL_APPROVAL_REQUIRED", "business-chat", "v1",
            ),),
        )
        self.options = Options(self.view)
        router = create_ai_task_submission_options_router(
            options=self.options,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(
            create_app(ai_task_create_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project}/ai-task-options"
        self.headers = {"cookie": "plm_session=" + "61" * 32}

    def test_default_closed_and_safe_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.get(self.path, headers=self.headers).status_code, 404)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()["data"]
        self.assertEqual(data["task_policies"][0]["reference"], "gap-analysis.v1")
        self.assertEqual(data["egress_policies"][0]["ttl_seconds"], 1800)
        self.assertEqual(data["routes"][0]["model_id"], str(self.model))
        for forbidden in ("endpoint.business", "https://", "secret", "prompt_template_id"):
            self.assertNotIn(forbidden, response.text.lower())

    def test_query_and_safe_errors_fail_closed(self):
        self.assertEqual(self.client.get(
            self.path + "?unexpected=1", headers=self.headers,
        ).status_code, 400)
        for code, status in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("AI_TASK_OPTIONS_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.options.failure = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(response.status_code, status)


if __name__ == "__main__":
    unittest.main()
