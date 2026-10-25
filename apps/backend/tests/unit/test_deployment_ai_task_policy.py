from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from plm_assistant.entrypoints.ai_task_policy import (
    DeploymentAITaskPolicyError, create_deployment_ai_task_policies,
)
from plm_assistant.entrypoints.production_login import _create_configured_ai_task_router
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings, load_bootstrap_settings,
)


class DeploymentAITaskPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.prompt_id = uuid.uuid4()
        self.policy = {
            "reference": "gap-analysis.v1",
            "policy_version": 1,
            "task_type": "GAP_ANALYSIS",
            "prompt_template_id": str(self.prompt_id),
            "purpose_ref": "project-gap-analysis.v1",
            "output_schema_ref": "gap-analysis-output.v1",
            "context_policy_ref": "project-documents.v1",
            "parameter_fields": [{
                "name": "language", "value_type": "STRING", "required": True,
                "max_length": 16, "minimum": None, "maximum": None,
                "allowed_values": ["zh-CN", "en-US"],
            }],
        }

    def settings(self, policies=(), *, complete=False):
        egress = ({
            "reference": "minimal-document-text.v1", "operation_types": ["AI_TASK"],
            "data_categories": ["DOCUMENT_TEXT"], "ttl_minutes": 30,
            "max_record_count": 50, "max_payload_bytes": 1_048_576,
            "max_input_tokens": 32_768, "max_retry_attempts": 2,
            "risk_codes": ["EXTERNAL_PROCESSING"],
            "approval_roles": ["PROJECT_MANAGER", "CUSTOMER_MANAGER"],
            "data_regions": ["cn-beijing"],
        },) if complete else ()
        execution = ({
            "reference": "endpoint.business.v1", "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": "https://business.example.test/v1/chat/completions",
            "data_region": "cn-beijing", "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
            "allowed_model_keys": ["business-chat"], "max_response_bytes": 1_048_576,
            "connect_timeout_seconds": 5, "read_timeout_seconds": 30,
            "total_timeout_seconds": 40,
        },) if complete else ()
        with patch.dict(os.environ, {}, clear=True):
            return BootstrapSettings(
                data_root=self.root, ai_task_policies=policies,
                ai_egress_policies=egress, ai_execution_policies=execution,
            )

    def test_missing_policy_fails_factory_and_keeps_write_mount_closed(self):
        settings = self.settings()
        with self.assertRaises(DeploymentAITaskPolicyError):
            create_deployment_ai_task_policies(settings)
        with patch("plm_assistant.entrypoints.production_login.create_windows_ai_task_router") as factory:
            result = _create_configured_ai_task_router(
                settings, runtime=MagicMock(), sessions=MagicMock(), origins=MagicMock(),
                license_guard=MagicMock(), audit=MagicMock(), documents=MagicMock(),
            )
        self.assertIsNone(result)
        factory.assert_not_called()

    def test_yaml_builds_immutable_submission_and_egress_purpose_policies(self):
        path = self.root / "bootstrap.yaml"
        path.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'ai_task_policies:\n'
            '  - reference: gap-analysis.v1\n'
            '    policy_version: 1\n'
            '    task_type: GAP_ANALYSIS\n'
            f'    prompt_template_id: "{self.prompt_id}"\n'
            '    purpose_ref: project-gap-analysis.v1\n'
            '    output_schema_ref: gap-analysis-output.v1\n'
            '    context_policy_ref: project-documents.v1\n'
            '    parameter_fields:\n'
            '      - name: language\n'
            '        value_type: STRING\n'
            '        required: true\n'
            '        max_length: 16\n'
            '        minimum: null\n'
            '        maximum: null\n'
            '        allowed_values: [zh-CN, en-US]\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            settings = load_bootstrap_settings(path)
        registry, purposes = create_deployment_ai_task_policies(settings)
        resolved = registry.resolve(
            reference="gap-analysis.v1", task_type="GAP_ANALYSIS",
            output_schema_ref="gap-analysis-output.v1",
            context_policy_ref="project-documents.v1",
            parameters={"language": "zh-CN"},
        )
        self.assertEqual(resolved.prompt_template_id, self.prompt_id)
        self.assertEqual(resolved.task_parameters_json, '{"language":"zh-CN"}')
        self.assertTrue(purposes.permits(
            task_type="GAP_ANALYSIS", purpose_ref="project-gap-analysis.v1",
        ))
        self.assertFalse(purposes.permits(
            task_type="GAP_ANALYSIS", purpose_ref="another-purpose.v1",
        ))

    def test_exact_bounded_non_secret_shape_is_enforced(self):
        invalid = (
            ({**self.policy, "api_key": "forbidden"},),
            ({key: value for key, value in self.policy.items()
              if key != "parameter_fields"},),
            (self.policy, self.policy),
            ({**self.policy, "policy_version": True},),
            ({**self.policy, "parameter_fields": [{
                **self.policy["parameter_fields"][0], "secret": "forbidden",
            }]},),
            tuple({**self.policy, "reference": f"policy.{index}"}
                  for index in range(65)),
        )
        for policies in invalid:
            with self.subTest(items=len(policies)):
                with self.assertRaises(ValueError):
                    self.settings(policies)

    def test_semantically_invalid_values_fail_without_disclosure(self):
        for changed in (
            {"reference": "bad reference"},
            {"prompt_template_id": str(self.prompt_id).upper()},
            {"policy_version": 0},
            {"parameter_fields": [{
                **self.policy["parameter_fields"][0], "value_type": "SECRET",
            }]},
        ):
            with self.subTest(changed=tuple(changed)):
                settings = self.settings(({**self.policy, **changed},))
                with self.assertRaises(DeploymentAITaskPolicyError) as caught:
                    create_deployment_ai_task_policies(settings)
                self.assertEqual(str(caught.exception),
                                 "AI Task deployment policy unavailable")

    def test_configured_write_mount_receives_both_policy_registries(self):
        settings = self.settings((self.policy,), complete=True)
        router = MagicMock(name="router")
        with patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_task_router",
            return_value=router,
        ) as factory:
            result = _create_configured_ai_task_router(
                settings, runtime=MagicMock(), sessions=MagicMock(), origins=MagicMock(),
                license_guard=MagicMock(), audit=MagicMock(), documents=MagicMock(),
            )
        self.assertIs(result, router)
        self.assertEqual(set(factory.call_args.kwargs), {
            "runtime", "sessions", "origins", "license_guard", "audit", "documents",
            "task_policies", "egress_purposes", "preview_policies",
            "execution_policies",
        })


if __name__ == "__main__":
    unittest.main()
