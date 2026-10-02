from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from plm_assistant.entrypoints.ai_egress_policy import (
    DeploymentAIEgressPolicyError,
    create_deployment_ai_egress_policies,
)
from plm_assistant.entrypoints.production_login import (
    _create_configured_ai_egress_router,
)
from plm_assistant.modules.ai.application.egress_authorization import EgressApprovalFacts
from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview,
    EgressPreviewView,
)
from plm_assistant.modules.ai.application.input_resolution import AIInputResourceVersionRef
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapConfigurationError,
    BootstrapSettings,
    load_bootstrap_settings,
)


class DeploymentAIEgressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.path = self.root / "bootstrap.yaml"
        self.policy = {
            "reference": "minimal-document-text.v1",
            "operation_types": ["AI_TASK"],
            "data_categories": ["DOCUMENT_TEXT"],
            "ttl_minutes": 30,
            "max_record_count": 50,
            "max_payload_bytes": 1_048_576,
            "max_input_tokens": 32_768,
            "max_retry_attempts": 2,
            "risk_codes": ["EXTERNAL_PROCESSING"],
            "approval_roles": ["PROJECT_MANAGER", "CUSTOMER_MANAGER"],
            "data_regions": ["cn-beijing"],
        }

    def settings(self, policies=()):
        with patch.dict(os.environ, {}, clear=True):
            return BootstrapSettings(data_root=self.root, ai_egress_policies=policies)

    def preview(self, *, region="cn-beijing") -> EgressPreviewView:
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        return EgressPreviewView(
            preview_id=uuid.uuid4(), project_id=uuid.uuid4(), purpose_ref="analysis.v1",
            operation_type="AI_TASK", provider_id=uuid.uuid4(),
            provider_config_version_id=uuid.uuid4(), model_id=uuid.uuid4(),
            data_region=region, allowed_data_categories=("DOCUMENT_TEXT",),
            source_refs=(), minimal_payload_policy_ref=self.policy["reference"],
            estimated_record_count=10, max_payload_bytes=1000, max_input_tokens=100,
            max_retry_attempts=1, payload_fingerprint=b"p" * 32,
            source_refs_fingerprint=b"s" * 32,
            risk_codes=("EXTERNAL_PROCESSING",), created_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    def facts(self, *, role="PROJECT_MANAGER", region="cn-beijing") -> EgressApprovalFacts:
        preview = self.preview(region=region)
        return EgressApprovalFacts(
            actor_id=uuid.uuid4(), project_role=role, preview=preview,
            allowed_data_categories=("DOCUMENT_TEXT",), max_record_count=10,
            max_payload_bytes=1000, max_input_tokens=100, max_retry_attempts=1,
            valid_until=preview.created_at + timedelta(minutes=10),
        )

    def test_missing_policy_fails_factory_but_keeps_write_mount_closed(self):
        settings = self.settings()
        with self.assertRaises(DeploymentAIEgressPolicyError) as caught:
            create_deployment_ai_egress_policies(settings)
        self.assertEqual(str(caught.exception), "AI Egress deployment policy unavailable")
        with patch("plm_assistant.entrypoints.production_login.create_windows_ai_egress_router") as factory:
            result = _create_configured_ai_egress_router(
                settings, runtime=MagicMock(), sessions=MagicMock(), origins=MagicMock(),
                license_guard=MagicMock(), audit=MagicMock(), documents=MagicMock(),
            )
        self.assertIsNone(result)
        factory.assert_not_called()

    def test_yaml_policy_builds_preview_and_role_region_approval(self):
        self.path.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'ai_egress_policies:\n'
            '  - reference: minimal-document-text.v1\n'
            '    operation_types: [AI_TASK]\n'
            '    data_categories: [DOCUMENT_TEXT]\n'
            '    ttl_minutes: 30\n'
            '    max_record_count: 50\n'
            '    max_payload_bytes: 1048576\n'
            '    max_input_tokens: 32768\n'
            '    max_retry_attempts: 2\n'
            '    risk_codes: [EXTERNAL_PROCESSING]\n'
            '    approval_roles: [PROJECT_MANAGER, CUSTOMER_MANAGER]\n'
            '    data_regions: [cn-beijing]\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            settings = load_bootstrap_settings(self.path)
        previews, approvals = create_deployment_ai_egress_policies(settings)
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        expires, risks = previews.authorize(CreateEgressPreview(
            session_token=b"a" * 32, csrf_token=b"b" * 32, trace_id=uuid.uuid4(),
            project_id=uuid.uuid4(), purpose_ref="analysis.v1", operation_type="AI_TASK",
            provider_id=uuid.uuid4(), model_id=uuid.uuid4(),
            source_refs=(AIInputResourceVersionRef("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            allowed_data_categories=("DOCUMENT_TEXT",),
            minimal_payload_policy_ref=self.policy["reference"], estimated_record_count=10,
            max_payload_bytes=1000, max_input_tokens=100, max_retry_attempts=1,
            payload_fingerprint=b"p" * 32,
        ), now=now)
        self.assertEqual(expires, now + timedelta(minutes=30))
        self.assertEqual(risks, ("EXTERNAL_PROCESSING",))
        self.assertTrue(approvals.permits(object(), facts=self.facts()))
        self.assertFalse(approvals.permits(object(), facts=self.facts(role="PROJECT_MEMBER")))
        self.assertFalse(approvals.permits(object(), facts=self.facts(region="cn-shanghai")))

    def test_exact_bounded_non_secret_shape_is_enforced(self):
        invalid = (
            ({**self.policy, "api_key": "forbidden"},),
            ({key: value for key, value in self.policy.items() if key != "risk_codes"},),
            (self.policy, self.policy),
            ({**self.policy, "ttl_minutes": True},),
            ({**self.policy, "data_categories": []},),
            ({**self.policy, "data_regions": ["cn-beijing", "cn-beijing"]},),
            tuple({**self.policy, "reference": f"policy.{index}"} for index in range(17)),
        )
        for policies in invalid:
            with self.subTest(items=len(policies)):
                with self.assertRaises(ValueError):
                    self.settings(policies)

    def test_semantically_invalid_values_fail_without_disclosure(self):
        for changed in (
            {"reference": "bad reference"},
            {"operation_types": ["UNFROZEN_OPERATION"]},
            {"data_categories": ["lowercase"]},
            {"risk_codes": ["bad-risk"]},
            {"approval_roles": ["ADMIN"]},
            {"data_regions": ["CN Beijing"]},
        ):
            with self.subTest(changed=tuple(changed)):
                settings = self.settings(({**self.policy, **changed},))
                with self.assertRaises(DeploymentAIEgressPolicyError) as caught:
                    create_deployment_ai_egress_policies(settings)
                self.assertEqual(str(caught.exception),
                                 "AI Egress deployment policy unavailable")

    def test_configured_write_mount_receives_immutable_policy_pair(self):
        settings = self.settings((self.policy,))
        router = MagicMock(name="router")
        with patch(
            "plm_assistant.entrypoints.production_login.create_windows_ai_egress_router",
            return_value=router,
        ) as factory:
            result = _create_configured_ai_egress_router(
                settings, runtime=MagicMock(), sessions=MagicMock(), origins=MagicMock(),
                license_guard=MagicMock(), audit=MagicMock(), documents=MagicMock(),
            )
        self.assertIs(result, router)
        kwargs = factory.call_args.kwargs
        self.assertEqual(set(kwargs), {
            "runtime", "sessions", "origins", "license_guard", "audit", "documents",
            "preview_policies", "approval_policy",
        })

    def test_duplicate_yaml_field_is_rejected(self):
        self.path.write_text(
            f'data_root: "{self.root.as_posix()}"\n'
            'ai_egress_policies:\n'
            '  - reference: first.policy\n'
            '    reference: second.policy\n',
            encoding="utf-8",
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BootstrapConfigurationError):
                load_bootstrap_settings(self.path)


if __name__ == "__main__":
    unittest.main()
