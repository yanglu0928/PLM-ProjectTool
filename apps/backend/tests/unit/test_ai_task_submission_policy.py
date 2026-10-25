from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField, AITaskPromptOwner, AITaskPromptOwnerError,
    AITaskPromptSnapshot, AITaskSubmissionPolicy, AITaskSubmissionPolicyError,
    AITaskSubmissionPolicyRegistry,
)


class _Repository:
    def __init__(self, result):
        self.result = result
        self.last = None

    def resolve_current(self, _transaction, *, policy):
        self.last = policy
        return self.result


class AITaskSubmissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = uuid.uuid4()
        self.policy = AITaskSubmissionPolicy(
            "prompt.gap.v1", 1, "GAP_ANALYSIS", self.template,
            "gap.analysis.v1", "schema.gap.v1", "rag.gap.v1",
            (AITaskParameterField("language", "STRING", True, 16,
                                  allowed_values=("zh-CN", "en-US")),
             AITaskParameterField("max_items", "INTEGER", False,
                                  minimum=1, maximum=100),
             AITaskParameterField("include_evidence", "BOOLEAN")),
        )
        self.registry = AITaskSubmissionPolicyRegistry({self.policy.reference: self.policy})

    def resolve(self, parameters=None):
        return self.registry.resolve(
            reference="prompt.gap.v1", task_type="GAP_ANALYSIS",
            output_schema_ref="schema.gap.v1", context_policy_ref="rag.gap.v1",
            parameters={"language": "zh-CN"} if parameters is None else parameters,
        )

    def test_strict_policy_returns_immutable_versioned_resolution(self):
        result = self.resolve({
            "max_items": 50, "language": "zh-CN", "include_evidence": True,
        })
        self.assertEqual((result.prompt_template_id, result.policy_version),
                         (self.template, 1))
        self.assertEqual(
            result.task_parameters_json,
            '{"include_evidence":true,"language":"zh-CN","max_items":50}',
        )

    def test_unknown_missing_or_wrong_typed_parameters_fail_closed(self):
        invalid = (
            {}, {"language": " zh-CN"}, {"language": "fr-FR"},
            {"language": "zh-CN", "max_items": True},
            {"language": "zh-CN", "max_items": 101},
            {"language": "zh-CN", "unknown": "value"},
        )
        for parameters in invalid:
            with self.subTest(parameters=parameters), self.assertRaises(
                    AITaskSubmissionPolicyError):
                self.resolve(parameters)

    def test_reference_task_and_schema_mismatch_fail_closed(self):
        variants = (
            {"reference": "prompt.other.v1"}, {"task_type": "SURVEY_ANALYZE"},
            {"output_schema_ref": "schema.other.v1"},
            {"context_policy_ref": "rag.other.v1"},
        )
        base = {
            "reference": "prompt.gap.v1", "task_type": "GAP_ANALYSIS",
            "output_schema_ref": "schema.gap.v1", "context_policy_ref": "rag.gap.v1",
            "parameters": {"language": "zh-CN"},
        }
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(
                    AITaskSubmissionPolicyError):
                self.registry.resolve(**(base | variant))

    def test_prompt_owner_revalidates_repository_projection(self):
        policy = self.resolve()
        snapshot = AITaskPromptSnapshot(
            self.template, 2, policy.reference, policy.policy_version,
            policy.purpose_ref, policy.output_schema_ref, policy.context_policy_ref,
            '{"language": "zh-CN"}', b"f" * 32,
        )
        repository = _Repository(snapshot)
        self.assertEqual(AITaskPromptOwner(repository).resolve_current(
            object(), policy=policy,
        ), snapshot)
        self.assertEqual(repository.last, policy)

        for invalid in (None, replace(snapshot, prompt_template_ref=uuid.uuid4()),
                        replace(snapshot, task_parameters_fingerprint=b"short")):
            with self.subTest(invalid=invalid):
                repository.result = invalid
                with self.assertRaises(AITaskPromptOwnerError):
                    AITaskPromptOwner(repository).resolve_current(object(), policy=policy)


if __name__ == "__main__":
    unittest.main()
