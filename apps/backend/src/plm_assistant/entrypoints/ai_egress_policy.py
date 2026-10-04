"""Fail-closed deployment source for non-secret AI Egress policies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType
from typing import Mapping

from plm_assistant.modules.ai.application.egress_authorization import (
    EgressApprovalFacts,
)
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicy,
    EgressPreviewPolicyRegistry,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


_REFERENCE = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_REGION = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_OPERATIONS = frozenset({"AI_TASK", "RETRIEVAL_RUN", "INDEX_BUILD", "INDEX_REBUILD"})
_APPROVAL_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class DeploymentAIEgressPolicyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Egress deployment policy unavailable")


@dataclass(frozen=True, slots=True)
class _ApprovalRule:
    roles: frozenset[str]
    regions: frozenset[str]


class DeploymentEgressApprovalPolicy:
    """Immutable role/region approval rules paired to preview policy references."""

    def __init__(self, rules: Mapping[str, _ApprovalRule]) -> None:
        if (not isinstance(rules, Mapping) or not rules
                or any(type(key) is not str or type(rule) is not _ApprovalRule
                       for key, rule in rules.items())):
            raise DeploymentAIEgressPolicyError()
        self._rules = MappingProxyType(dict(rules))

    def permits(self, transaction: object, *, facts: EgressApprovalFacts) -> bool:
        del transaction
        if type(facts) is not EgressApprovalFacts:
            return False
        rule = self._rules.get(facts.preview.minimal_payload_policy_ref)
        return bool(rule is not None
                    and facts.project_role in rule.roles
                    and facts.preview.data_region in rule.regions)


def create_deployment_ai_egress_policies(
    settings: BootstrapSettings,
) -> tuple[EgressPreviewPolicyRegistry, DeploymentEgressApprovalPolicy]:
    """Snapshot an explicit Bootstrap policy without accepting URLs or secrets."""
    try:
        if type(settings) is not BootstrapSettings or not settings.ai_egress_policies:
            raise DeploymentAIEgressPolicyError()
        previews: dict[str, EgressPreviewPolicy] = {}
        approvals: dict[str, _ApprovalRule] = {}
        for item in settings.ai_egress_policies:
            reference = item["reference"]
            operations = frozenset(item["operation_types"])
            categories = frozenset(item["data_categories"])
            risks = tuple(item["risk_codes"])
            roles = frozenset(item["approval_roles"])
            regions = frozenset(item["data_regions"])
            if (_REFERENCE.fullmatch(reference) is None
                    or not operations.issubset(_OPERATIONS)
                    or not roles.issubset(_APPROVAL_ROLES)
                    or any(_CODE.fullmatch(value) is None
                           for value in (*categories, *risks))
                    or any(_REGION.fullmatch(value) is None for value in regions)
                    or reference in previews):
                raise DeploymentAIEgressPolicyError()
            previews[reference] = EgressPreviewPolicy(
                reference=reference,
                allowed_operation_types=operations,
                allowed_data_categories=categories,
                ttl=timedelta(minutes=item["ttl_minutes"]),
                max_record_count=item["max_record_count"],
                max_payload_bytes=item["max_payload_bytes"],
                max_input_tokens=item["max_input_tokens"],
                max_retry_attempts=item["max_retry_attempts"],
                risk_codes=risks,
            )
            approvals[reference] = _ApprovalRule(roles=roles, regions=regions)
        return (
            EgressPreviewPolicyRegistry(previews),
            DeploymentEgressApprovalPolicy(approvals),
        )
    except DeploymentAIEgressPolicyError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError):
        raise DeploymentAIEgressPolicyError() from None
