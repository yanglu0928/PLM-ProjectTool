from __future__ import annotations

import unittest
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy, EgressPreviewPolicyRegistry,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy, AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.application.task_submission_options import (
    AITaskRouteCandidate, AITaskSubmissionOptionsError,
    AITaskSubmissionOptionsService, GetAITaskSubmissionOptions,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


class Guard:
    def require_valid(self, *, trace_id):
        return trace_id


class Access:
    actor = uuid.uuid4()
    def authenticated_user(self, transaction, *, session_token, csrf_token, now):
        return self.actor


class Authorization:
    def require_in_transaction(self, transaction, *, user_id, project_id, operation):
        if operation != "AI_TASK_OPTIONS_GET":
            raise AssertionError(operation)
        return AuthorizedProjectAction(user_id, project_id, operation, "PROJECT_MANAGER")


class Repository:
    routes = ()
    def list_routes(self, transaction, *, limit):
        if limit != 201:
            raise AssertionError(limit)
        return self.routes


class AITaskSubmissionOptionsTests(unittest.TestCase):
    def setUp(self):
        self.project, self.trace = uuid.uuid4(), uuid.uuid4()
        self.route = AITaskRouteCandidate(
            uuid.uuid4(), uuid.uuid4(), "合成服务", "cn-beijing",
            ProviderKind.OPENAI_COMPATIBLE, "endpoint.business.v1",
            "EXTERNAL_APPROVAL_REQUIRED", "business-chat", "v1",
        )
        self.repo = Repository()
        self.repo.routes = (self.route, AITaskRouteCandidate(
            uuid.uuid4(), uuid.uuid4(), "未授权服务", "cn-beijing",
            ProviderKind.OPENAI_COMPATIBLE, "endpoint.other.v1",
            "EXTERNAL_APPROVAL_REQUIRED", "other-chat", "v1",
        ))
        tasks = AITaskSubmissionPolicyRegistry({"gap-analysis.v1": AITaskSubmissionPolicy(
            "gap-analysis.v1", 1, "GAP_ANALYSIS", uuid.uuid4(),
            "project-gap-analysis.v1", "gap-output.v2", "no-retrieval.v1",
            (AITaskParameterField("language", "STRING", True, 16,
                                  allowed_values=("zh-CN",)),),
        )})
        egress = EgressPreviewPolicyRegistry({"minimal-document-text.v1": EgressPreviewPolicy(
            "minimal-document-text.v1", frozenset({"AI_TASK"}),
            frozenset({"DOCUMENT_TEXT"}), timedelta(minutes=30), 50,
            1_048_576, 32_768, 2, ("EXTERNAL_PROCESSING",),
        )})
        execution = AIProviderExecutionPolicyRegistry((AIProviderExecutionPolicy(
            "endpoint.business.v1", ProviderKind.OPENAI_COMPATIBLE,
            "https://business.example.test/v1/chat/completions", "cn-beijing",
            "EXTERNAL_APPROVAL_REQUIRED", frozenset({"business-chat"}),
            1_048_576, 5, 30, 40,
        ),))
        self.service = AITaskSubmissionOptionsService(
            unit_of_work=lambda: nullcontext(object()), access=Access(),
            license_guard=Guard(), authorization=Authorization(), repository=self.repo,
            task_policies=tasks, egress_policies=egress,
            execution_policies=execution,
            clock=lambda: datetime(2026, 10, 3, tzinfo=timezone.utc),
        )

    def test_returns_only_execution_allowlisted_current_route(self):
        view = self.service.get(GetAITaskSubmissionOptions(
            b"s" * 32, self.trace, self.project,
        ))
        self.assertEqual(view.routes, (self.route,))
        self.assertEqual(view.task_policies[0].reference, "gap-analysis.v1")
        self.assertEqual(view.egress_policies[0].reference, "minimal-document-text.v1")
        self.assertNotIn("https://", repr(view.routes))

    def test_invalid_identity_and_oversized_repository_fail_closed(self):
        access = self.service._access
        access.actor = None
        with self.assertRaises(AITaskSubmissionOptionsError) as caught:
            self.service.get(GetAITaskSubmissionOptions(b"s" * 32, self.trace, self.project))
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        access.actor = uuid.uuid4()
        self.repo.routes = tuple(self.route for _ in range(201))
        with self.assertRaises(AITaskSubmissionOptionsError):
            self.service.get(GetAITaskSubmissionOptions(b"s" * 32, self.trace, self.project))


if __name__ == "__main__":
    unittest.main()
