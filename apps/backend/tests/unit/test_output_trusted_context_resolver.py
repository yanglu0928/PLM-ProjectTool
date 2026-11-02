from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest,
    OutputRequestError,
)
from plm_assistant.modules.output.application.resolve_context import (
    FixedSourceVersion,
    OutputPolicyVersion,
    OutputTemplateVersion,
    PluginOperationCapability,
    TrustedOutputContextResolver,
)


class Sources:
    def __init__(self, rows):
        self.rows = rows

    def read_authorized_fixed_version(self, _tx, *, actor_id, project_id, source_version_ref):
        del actor_id
        row = self.rows.get(source_version_ref)
        if row is not None and row.project_id != project_id:
            return row
        return row


class Templates:
    def __init__(self, value):
        self.value = value

    def get_immutable_version(self, _tx, *, template_version_ref):
        return self.value if self.value and self.value.template_version_ref == template_version_ref else None


class Policies:
    def __init__(self, value):
        self.value = value

    def get_policy(self, _tx, *, policy_ref):
        return self.value if self.value and self.value.policy_ref == policy_ref else None


class Operations:
    def __init__(self, value):
        self.value = value

    def get_operation(self, _tx, *, operation_id):
        return self.value if self.value and self.value.operation_id == operation_id else None


class TrustedOutputContextResolverTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.template_ref, self.source_ref = [
            uuid.uuid4() for _ in range(4)
        ]
        self.command = CreateOutputRequest(
            b"session", b"csrf", uuid.uuid4(), self.project, "DOCX",
            self.template_ref, (self.source_ref,), "policy.standard.v1",
            "word.generate",
        )
        self.sources = Sources({
            self.source_ref: FixedSourceVersion(
                self.project, self.source_ref, "PLAN_VERSION", "APPROVED", True,
                {"title": "Approved plan", "body": "authorized content",
                 "local_path": "D:/private/file", "secret": "never copy"},
            )
        })
        self.templates = Templates(OutputTemplateVersion(
            self.template_ref, "DOCX", ("PLAN_VERSION",)))
        self.policies = Policies(OutputPolicyVersion(
            "policy.standard.v1", (self.template_ref,), ("DOCX",),
            ("word.generate",), ("APPROVED",),
            {"PLAN_VERSION": ("title", "body")},
            max_sources=4, max_context_bytes=8192,
        ))
        self.operations = Operations(PluginOperationCapability(
            "word.generate", ("DOCX",)))
        self.resolver = TrustedOutputContextResolver(
            sources=self.sources, templates=self.templates,
            policies=self.policies, operations=self.operations)

    def test_resolves_only_fixed_authorized_minimal_context(self):
        result = self.resolver.resolve(
            object(), actor_id=self.actor, command=self.command)
        self.assertEqual(result.source_version_refs, (self.source_ref,))
        self.assertEqual(result.context_payload["sources"][0]["fields"], {
            "title": "Approved plan", "body": "authorized content"})
        self.assertNotIn("local_path", str(result.context_payload))
        self.assertNotIn("never copy", str(result.context_payload))
        self.assertEqual(len(result.context_fingerprint), 32)

    def test_fingerprint_is_stable_for_same_fixed_inputs(self):
        first = self.resolver.resolve(object(), actor_id=self.actor, command=self.command)
        second = self.resolver.resolve(object(), actor_id=self.actor, command=self.command)
        self.assertEqual(first.context_fingerprint, second.context_fingerprint)

    def test_rejects_missing_template_policy_or_operation(self):
        for attr, replacement in (
            ("_templates", Templates(None)),
            ("_policies", Policies(None)),
            ("_operations", Operations(None)),
        ):
            with self.subTest(attr=attr):
                old = getattr(self.resolver, attr)
                setattr(self.resolver, attr, replacement)
                with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
                    self.resolver.resolve(object(), actor_id=self.actor, command=self.command)
                setattr(self.resolver, attr, old)

    def test_rejects_cross_project_source(self):
        self.sources.rows[self.source_ref] = FixedSourceVersion(
            uuid.uuid4(), self.source_ref, "PLAN_VERSION", "APPROVED", True, {})
        with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
            self.resolver.resolve(object(), actor_id=self.actor, command=self.command)

    def test_rejects_unauthorized_or_unapproved_source(self):
        for authorized, state in ((False, "APPROVED"), (True, "DRAFT")):
            with self.subTest(authorized=authorized, state=state):
                self.sources.rows[self.source_ref] = FixedSourceVersion(
                    self.project, self.source_ref, "PLAN_VERSION", state, authorized, {})
                with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
                    self.resolver.resolve(object(), actor_id=self.actor, command=self.command)

    def test_rejects_unpublished_or_mutable_template(self):
        for immutable, published in ((False, True), (True, False)):
            with self.subTest(immutable=immutable, published=published):
                self.templates.value = OutputTemplateVersion(
                    self.template_ref, "DOCX", ("PLAN_VERSION",),
                    immutable=immutable, published=published)
                with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
                    self.resolver.resolve(object(), actor_id=self.actor, command=self.command)

    def test_rejects_incompatible_output_type_and_operation(self):
        self.templates.value = OutputTemplateVersion(
            self.template_ref, "PPTX", ("PLAN_VERSION",))
        with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
            self.resolver.resolve(object(), actor_id=self.actor, command=self.command)

    def test_rejects_untrusted_operation_and_oversized_context(self):
        self.operations.value = PluginOperationCapability(
            "word.generate", ("DOCX",), trusted=False)
        with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
            self.resolver.resolve(object(), actor_id=self.actor, command=self.command)
        self.setUp()
        self.policies.value = OutputPolicyVersion(
            "policy.standard.v1", (self.template_ref,), ("DOCX",),
            ("word.generate",), ("APPROVED",),
            {"PLAN_VERSION": ("body",)}, max_sources=4, max_context_bytes=20)
        with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
            self.resolver.resolve(object(), actor_id=self.actor, command=self.command)

    def test_rejects_non_json_or_deep_projection(self):
        for bad in (object(), {"nested": {"too": {"deep": {"deeper": {"x": "y"}}}}}):
            with self.subTest(bad=type(bad).__name__):
                self.sources.rows[self.source_ref] = FixedSourceVersion(
                    self.project, self.source_ref, "PLAN_VERSION", "APPROVED",
                    True, {"body": bad})
                self.policies.value = OutputPolicyVersion(
                    "policy.standard.v1", (self.template_ref,), ("DOCX",),
                    ("word.generate",), ("APPROVED",),
                    {"PLAN_VERSION": ("body",)}, max_sources=4,
                    max_context_bytes=8192)
                with self.assertRaisesRegex(OutputRequestError, "VALIDATION_FAILED"):
                    self.resolver.resolve(object(), actor_id=self.actor, command=self.command)


if __name__ == "__main__":
    unittest.main()
