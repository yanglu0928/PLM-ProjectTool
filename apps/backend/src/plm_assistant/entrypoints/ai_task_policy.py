"""Fail-closed deployment source for non-secret AI Task submission policies."""

from __future__ import annotations

import uuid

from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry,
)
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskParameterField,
    AITaskSubmissionPolicy,
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


class DeploymentAITaskPolicyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Task deployment policy unavailable")


def create_deployment_ai_task_policies(
    settings: BootstrapSettings,
) -> tuple[AITaskSubmissionPolicyRegistry, AITaskEgressPurposeRegistry]:
    """Snapshot explicit Task policies and derive their allowed Egress purposes."""
    try:
        if type(settings) is not BootstrapSettings or not settings.ai_task_policies:
            raise DeploymentAITaskPolicyError()
        policies: dict[str, AITaskSubmissionPolicy] = {}
        purposes: dict[str, set[str]] = {}
        for item in settings.ai_task_policies:
            prompt_template_id = uuid.UUID(item["prompt_template_id"])
            if str(prompt_template_id) != item["prompt_template_id"]:
                raise DeploymentAITaskPolicyError()
            policy = AITaskSubmissionPolicy(
                reference=item["reference"],
                policy_version=item["policy_version"],
                task_type=item["task_type"],
                prompt_template_id=prompt_template_id,
                purpose_ref=item["purpose_ref"],
                output_schema_ref=item["output_schema_ref"],
                context_policy_ref=item["context_policy_ref"],
                parameter_fields=tuple(AITaskParameterField(**field)
                                       for field in item["parameter_fields"]),
            )
            if policy.reference in policies:
                raise DeploymentAITaskPolicyError()
            policies[policy.reference] = policy
            purposes.setdefault(policy.task_type, set()).add(policy.purpose_ref)
        return (
            AITaskSubmissionPolicyRegistry(policies),
            AITaskEgressPurposeRegistry({
                task_type: frozenset(values) for task_type, values in purposes.items()
            }),
        )
    except DeploymentAITaskPolicyError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise DeploymentAITaskPolicyError() from None
