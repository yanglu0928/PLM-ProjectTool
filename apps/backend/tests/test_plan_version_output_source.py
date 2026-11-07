from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from plm_assistant.entrypoints.output_fixed_source_adapter import (
    FixedOutputSourceAdapter,
)
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest, OutputRequestError,
)
from plm_assistant.modules.output.application.resolve_context import (
    FixedSourceVersion, PluginOperationCapability, TrustedOutputContextResolver,
)
from plm_assistant.modules.output.infrastructure.builtin_policy_registry import (
    BUILTIN_PLAN_DOCX_POLICY_REF, BUILTIN_REQUIREMENT_DOCX_POLICY_REF,
    BuiltinOutputPolicyRegistry,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID,
    BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
    BuiltinOutputTemplateRegistry,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanOutputSourceProjection, PlanVersionReadError, PlanVersionReadService,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementOutputSourceProjection, RequirementVersionReadError,
)


def _id() -> uuid.UUID:
    return uuid.uuid4()


class _Authorization:
    def __init__(self, result=None):
        self.result = result

    def require_in_transaction(self, transaction, *, user_id, project_id, operation):
        assert transaction == "tx"
        assert operation == "PLAN_VERSION_GET"
        if self.result is not None:
            return self.result
        return SimpleNamespace(
            user_id=user_id, project_id=project_id, operation=operation,
        )


class _Repository:
    def __init__(self, projection):
        self.projection = projection
        self.calls = []

    def get_output_source(self, transaction, *, project_id, plan_version_id):
        self.calls.append((transaction, project_id, plan_version_id))
        return self.projection


def _service(project_id, projection, authorization=None):
    return PlanVersionReadService(
        unit_of_work=lambda: None, access=object(), license_guard=object(),
        authorization=authorization or _Authorization(),
        repository=_Repository(projection),
    )


def test_plan_output_projection_uses_exact_ref_and_owner_authorization():
    actor, project, version = _id(), _id(), _id()
    projection = PlanOutputSourceProjection(
        plan_version_id=version, project_id=project, version_state="APPROVED",
        fields={"version_no": 3, "wbs_items": [{"title": "synthetic"}]},
    )
    repo = _Repository(projection)
    service = PlanVersionReadService(
        unit_of_work=lambda: None, access=object(), license_guard=object(),
        authorization=_Authorization(), repository=repo,
    )

    result = service.read_output_source(
        "tx", actor_id=actor, project_id=project, plan_version_id=version,
    )

    assert result is projection
    assert repo.calls == [("tx", project, version)]


def test_plan_output_projection_hides_wrong_project_and_invalid_ref():
    actor, project, other, version = _id(), _id(), _id(), _id()
    mismatched = PlanOutputSourceProjection(
        plan_version_id=version, project_id=other, version_state="APPROVED",
        fields={"version_no": 1},
    )
    service = _service(project, mismatched)

    with pytest.raises(PlanVersionReadError) as caught:
        service.read_output_source(
            "tx", actor_id=actor, project_id=project, plan_version_id=version,
        )
    assert caught.value.code == "RESOURCE_NOT_FOUND"

    with pytest.raises(PlanVersionReadError):
        service.read_output_source(
            "tx", actor_id=actor, project_id=project, plan_version_id=uuid.UUID(int=0),
        )


def test_plan_output_projection_rechecks_transaction_authorization():
    actor, project, version, other = _id(), _id(), _id(), _id()
    denied = SimpleNamespace(user_id=actor, project_id=other, operation="PLAN_VERSION_GET")
    service = _service(project, None, _Authorization(denied))

    with pytest.raises(PlanVersionReadError) as caught:
        service.read_output_source(
            "tx", actor_id=actor, project_id=project, plan_version_id=version,
        )
    assert caught.value.code == "RESOURCE_NOT_FOUND"


class _RequirementReader:
    def __init__(self, projection=None, error=None):
        self.projection, self.error = projection, error

    def read_output_source(self, transaction, **kwargs):
        if self.error:
            raise self.error
        if self.projection:
            assert kwargs["requirement_version_id"] == self.projection.requirement_version_id
        return self.projection


class _PlanReader:
    def __init__(self, projection=None, error=None):
        self.projection, self.error = projection, error

    def read_output_source(self, transaction, **kwargs):
        if self.error:
            raise self.error
        if self.projection:
            assert kwargs["plan_version_id"] == self.projection.plan_version_id
        return self.projection


def test_composite_adapter_returns_only_the_matching_owner_projection():
    actor, project, version = _id(), _id(), _id()
    plan = PlanOutputSourceProjection(
        plan_version_id=version, project_id=project, version_state="APPROVED",
        fields={"version_no": 2},
    )
    adapter = FixedOutputSourceAdapter(
        requirements=_RequirementReader(error=RequirementVersionReadError("RESOURCE_NOT_FOUND")),
        plans=_PlanReader(plan),
    )

    result = adapter.read_authorized_fixed_version(
        "tx", actor_id=actor, project_id=project, source_version_ref=version,
    )

    assert result is not None
    assert result.source_kind == "PLAN_VERSION"
    assert result.source_version_ref == version
    assert result.authorized is True


def test_composite_adapter_rejects_ambiguous_cross_owner_uuid():
    actor, project, version = _id(), _id(), _id()
    requirement = RequirementOutputSourceProjection(
        requirement_version_id=version, project_id=project,
        version_state="APPROVED", fields={"title": "synthetic"},
    )
    plan = PlanOutputSourceProjection(
        plan_version_id=version, project_id=project, version_state="APPROVED",
        fields={"version_no": 1},
    )
    adapter = FixedOutputSourceAdapter(
        requirements=_RequirementReader(requirement),
        plans=_PlanReader(plan),
    )

    assert adapter.read_authorized_fixed_version(
        "tx", actor_id=actor, project_id=project, source_version_ref=version,
    ) is None


def test_builtin_plan_template_and_policy_are_appended_without_replacing_requirement():
    templates = BuiltinOutputTemplateRegistry()
    policies = BuiltinOutputPolicyRegistry()

    old_template = templates.get_immutable_version(
        None, template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
    )
    new_template = templates.get_immutable_version(
        None, template_version_ref=BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID,
    )
    old_policy = policies.get_policy(
        None, policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF,
    )
    new_policy = policies.get_policy(
        None, policy_ref=BUILTIN_PLAN_DOCX_POLICY_REF,
    )

    assert old_template is not None and old_template.source_kinds == ("REQUIREMENT_VERSION",)
    assert new_template is not None and new_template.source_kinds == ("PLAN_VERSION",)
    assert old_policy is not None and "REQUIREMENT_VERSION" in old_policy.fields_by_source_kind
    assert new_policy is not None and tuple(new_policy.fields_by_source_kind) == ("PLAN_VERSION",)
    assert new_policy.max_sources == 1


class _SourcePort:
    def __init__(self, source):
        self.source = source

    def read_authorized_fixed_version(self, transaction, **kwargs):
        return self.source


class _PlanPolicy:
    def get_policy(self, transaction, *, policy_ref):
        return BuiltinOutputPolicyRegistry().get_policy(
            transaction, policy_ref=policy_ref,
        )


class _PlanTemplate:
    def get_immutable_version(self, transaction, *, template_version_ref):
        return BuiltinOutputTemplateRegistry().get_immutable_version(
            transaction, template_version_ref=template_version_ref,
        )


class _TrustedOperation:
    def get_operation(self, transaction, *, operation_id):
        return PluginOperationCapability(
            operation_id=operation_id, output_types=("DOCX",),
            enabled=True, trusted=True,
        )


def test_plan_output_resolver_projects_allowlisted_approved_snapshot_fields():
    actor, project, version = _id(), _id(), _id()
    source = FixedSourceVersion(
        project_id=project, source_version_ref=version,
        source_kind="PLAN_VERSION", review_state="APPROVED", authorized=True,
        fields={
            "version_no": 4, "wbs_items": [{"title": "synthetic"}],
            "dependencies": [], "milestones": [], "exclusions": [],
            "unapproved_internal_field": "must not enter context",
        },
    )
    resolver = TrustedOutputContextResolver(
        sources=_SourcePort(source), templates=_PlanTemplate(),
        policies=_PlanPolicy(), operations=_TrustedOperation(),
    )
    command = CreateOutputRequest(
        session_token=b"s" * 32, csrf_token=b"c" * 32,
        trace_id=_id(), project_id=project, output_type="DOCX",
        template_version_ref=BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID,
        source_version_refs=(version,),
        output_policy_ref=BUILTIN_PLAN_DOCX_POLICY_REF,
        plugin_operation="word.generate",
    )

    resolved = resolver.resolve("tx", actor_id=actor, command=command)

    fields = resolved.context_payload["sources"][0]["fields"]
    assert fields == {
        "version_no": 4, "wbs_items": [{"title": "synthetic"}],
        "dependencies": [], "milestones": [], "exclusions": [],
    }


def test_plan_output_resolver_rejects_unapproved_plan_version():
    actor, project, version = _id(), _id(), _id()
    source = FixedSourceVersion(
        project_id=project, source_version_ref=version,
        source_kind="PLAN_VERSION", review_state="DRAFT", authorized=True,
        fields={"version_no": 1, "wbs_items": [], "dependencies": [],
                "milestones": [], "exclusions": []},
    )
    resolver = TrustedOutputContextResolver(
        sources=_SourcePort(source), templates=_PlanTemplate(),
        policies=_PlanPolicy(), operations=_TrustedOperation(),
    )
    command = CreateOutputRequest(
        session_token=b"s" * 32, csrf_token=b"c" * 32,
        trace_id=_id(), project_id=project, output_type="DOCX",
        template_version_ref=BUILTIN_PLAN_DOCX_TEMPLATE_VERSION_ID,
        source_version_refs=(version,),
        output_policy_ref=BUILTIN_PLAN_DOCX_POLICY_REF,
        plugin_operation="word.generate",
    )

    with pytest.raises(OutputRequestError):
        resolver.resolve("tx", actor_id=actor, command=command)


def test_composite_adapter_does_not_mask_other_owner_permission():
    actor, project, version = _id(), _id(), _id()
    plan = PlanOutputSourceProjection(
        plan_version_id=version, project_id=project, version_state="APPROVED",
        fields={"version_no": 2},
    )
    adapter = FixedOutputSourceAdapter(
        requirements=_RequirementReader(
            error=RequirementVersionReadError("AUTH_ACCESS_DENIED"),
        ),
        plans=_PlanReader(plan),
    )

    result = adapter.read_authorized_fixed_version(
        "tx", actor_id=actor, project_id=project, source_version_ref=version,
    )

    assert result is not None
    assert result.source_kind == "PLAN_VERSION"
