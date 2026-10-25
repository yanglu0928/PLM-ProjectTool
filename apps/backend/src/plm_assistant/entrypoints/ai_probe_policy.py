"""Fail-closed deployment source for non-secret AI Provider probe policies."""

from __future__ import annotations

from plm_assistant.modules.ai.application.probe_policy import (
    EndpointProbePolicy, EndpointProbeRegistry, ProbePolicyError,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class DeploymentAIProbePolicyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Provider probe policy unavailable")


def create_deployment_ai_probe_registry(settings: BootstrapSettings) -> EndpointProbeRegistry:
    """Snapshot the explicit Bootstrap policy; never derive a URL from Provider input."""
    try:
        if type(settings) is not BootstrapSettings or not settings.ai_probe_policies:
            raise DeploymentAIProbePolicyError()
        policies = {}
        for item in settings.ai_probe_policies:
            policy = EndpointProbePolicy(
                reference=item["reference"], kind=ProviderKind(item["kind"]),
                endpoint_url=item["endpoint_url"], model_key=item["model_key"],
                data_region=item["data_region"], egress_class=item["egress_class"],
            )
            if policy.reference in policies:
                raise DeploymentAIProbePolicyError()
            policies[policy.reference] = policy
        return EndpointProbeRegistry(policies)
    except (AttributeError, KeyError, TypeError, ValueError, ProbePolicyError):
        raise DeploymentAIProbePolicyError() from None
