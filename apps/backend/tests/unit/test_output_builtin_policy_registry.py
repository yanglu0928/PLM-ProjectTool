from __future__ import annotations

import unittest
import uuid
from types import MappingProxyType

from plm_assistant.modules.output.application.create_request import CreateOutputRequest
from plm_assistant.modules.output.application.resolve_context import (
    FixedSourceVersion,
    OutputPolicyVersion,
    PluginOperationCapability,
    TrustedOutputContextResolver,
)
from plm_assistant.modules.output.infrastructure.builtin_policy_registry import (
    BUILTIN_REQUIREMENT_DOCX_POLICY_REF,
    BuiltinOutputPolicyRegistry,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
    BuiltinOutputTemplateRegistry,
)


class SyntheticSources:
    def __init__(self, source: FixedSourceVersion):
        self.source = source

    def read_authorized_fixed_version(self, _tx, **_kwargs):
        return self.source


class SyntheticOperation:
    """Test-only trusted operation fact; not production registry evidence."""

    def get_operation(self, _tx, *, operation_id):
        if operation_id != "word.generate":
            return None
        return PluginOperationCapability(
            "word.generate", ("DOCX",), enabled=True, trusted=True)


class BuiltinOutputPolicyRegistryTests(unittest.TestCase):
    def test_returns_exact_fixed_policy_and_narrow_allowlist(self):
        registry = BuiltinOutputPolicyRegistry()
        policy = registry.get_policy(
            object(), policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF)
        self.assertEqual(policy.allowed_template_versions, (
            BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,))
        self.assertEqual(policy.allowed_output_types, ("DOCX",))
        self.assertEqual(policy.allowed_plugin_operations, ("word.generate",))
        self.assertEqual(policy.allowed_review_states, ("APPROVED",))
        self.assertEqual(dict(policy.fields_by_source_kind), {
            "REQUIREMENT_VERSION": (
                "title", "statement", "acceptance_criteria",)})
        self.assertEqual(policy.max_sources, 4)
        self.assertEqual(policy.max_context_bytes, 8192)

    def test_unknown_and_invalid_policy_refs_fail_closed(self):
        registry = BuiltinOutputPolicyRegistry()
        for ref in ("output.policy.unknown.v1", None, "", 5):
            with self.subTest(ref=ref):
                self.assertIsNone(registry.get_policy(
                    object(), policy_ref=ref))

    def test_catalog_is_immutable(self):
        registry = BuiltinOutputPolicyRegistry()
        with self.assertRaises(TypeError):
            registry._catalog["unexpected"] = registry.get_policy(
                None, policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF)
        policy = registry.get_policy(
            None, policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF)
        self.assertIsInstance(policy.fields_by_source_kind, MappingProxyType)
        with self.assertRaises(TypeError):
            policy.fields_by_source_kind["REQUIREMENT_VERSION"] = ("title",)

    def test_duplicate_or_broadened_policy_is_rejected(self):
        valid = BuiltinOutputPolicyRegistry().get_policy(
            None, policy_ref=BUILTIN_REQUIREMENT_DOCX_POLICY_REF)
        broadened = OutputPolicyVersion(
            policy_ref="output.policy.broadened.v1",
            allowed_template_versions=valid.allowed_template_versions,
            allowed_output_types=("DOCX", "PPTX"),
            allowed_plugin_operations=valid.allowed_plugin_operations,
            allowed_review_states=valid.allowed_review_states,
            fields_by_source_kind=valid.fields_by_source_kind,
            max_sources=4,
            max_context_bytes=8192,
        )
        with self.assertRaisesRegex(ValueError, "catalog is invalid"):
            BuiltinOutputPolicyRegistry((valid, valid))
        with self.assertRaisesRegex(ValueError, "catalog is invalid"):
            BuiltinOutputPolicyRegistry((broadened,))
        with self.assertRaisesRegex(ValueError, "catalog is invalid"):
            BuiltinOutputPolicyRegistry(())

    def test_resolver_projects_only_policy_allowed_requirement_fields(self):
        actor, project, source_ref = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        source = FixedSourceVersion(
            project, source_ref, "REQUIREMENT_VERSION", "APPROVED", True,
            {"title": "Synthetic", "statement": "Need",
             "acceptance_criteria": [{"observable_result": "Done"}],
             "rationale": "not in the minimal policy"},
        )
        command = CreateOutputRequest(
            b"session", b"csrf", uuid.uuid4(), project, "DOCX",
            BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID, (source_ref,),
            BUILTIN_REQUIREMENT_DOCX_POLICY_REF, "word.generate",
        )
        resolver = TrustedOutputContextResolver(
            sources=SyntheticSources(source),
            templates=BuiltinOutputTemplateRegistry(),
            policies=BuiltinOutputPolicyRegistry(),
            operations=SyntheticOperation(),
        )
        result = resolver.resolve(object(), actor_id=actor, command=command)
        fields = result.context_payload["sources"][0]["fields"]
        self.assertEqual(set(fields), {
            "title", "statement", "acceptance_criteria"})
        self.assertNotIn("rationale", fields)


if __name__ == "__main__":
    unittest.main()
