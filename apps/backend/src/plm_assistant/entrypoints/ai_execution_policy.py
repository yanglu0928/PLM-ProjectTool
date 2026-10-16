"""Fail-closed deployment source for non-secret AI execution policies."""

from __future__ import annotations

from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
)
from plm_assistant.modules.ai.application.provider_execution_policy import (
    AIProviderExecutionPolicy,
    AIProviderExecutionPolicyRegistry,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)


class DeploymentAIExecutionPolicyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Provider execution policy unavailable")


def create_deployment_ai_execution_registry(
    settings: BootstrapSettings,
) -> AIProviderExecutionPolicyRegistry:
    """Snapshot allowlisted endpoints and bounds; never accept a Provider key."""
    try:
        if (type(settings) is not BootstrapSettings
                or not settings.ai_execution_policies):
            raise DeploymentAIExecutionPolicyError()
        policies = []
        for item in settings.ai_execution_policies:
            policies.append(AIProviderExecutionPolicy(
                reference=item["reference"],
                provider_kind=ProviderKind(item["kind"]),
                endpoint_url=item["endpoint_url"],
                data_region=item["data_region"],
                egress_class=item["egress_class"],
                allowed_model_keys=frozenset(item["allowed_model_keys"]),
                max_response_bytes=item["max_response_bytes"],
                connect_timeout_seconds=item["connect_timeout_seconds"],
                read_timeout_seconds=item["read_timeout_seconds"],
                total_timeout_seconds=item["total_timeout_seconds"],
            ))
        return AIProviderExecutionPolicyRegistry(policies)
    except DeploymentAIExecutionPolicyError:
        raise
    except (
        AttributeError, KeyError, TypeError, ValueError,
        AIProviderExecutionError,
    ):
        raise DeploymentAIExecutionPolicyError() from None
