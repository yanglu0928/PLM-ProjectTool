from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.output.application.resolve_context import (
    OutputTemplateVersion,
)
from plm_assistant.modules.output.infrastructure.builtin_template_registry import (
    BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
    BuiltinOutputTemplateRegistry,
)


class BuiltinOutputTemplateRegistryTests(unittest.TestCase):
    def test_resolves_one_stable_immutable_docx_template_version(self):
        registry = BuiltinOutputTemplateRegistry()
        template = registry.get_immutable_version(
            object(),
            template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
        )
        self.assertEqual(
            template,
            OutputTemplateVersion(
                BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
                "DOCX",
                ("REQUIREMENT_VERSION",),
                immutable=True,
                published=True,
            ),
        )
        self.assertIs(
            registry.get_immutable_version(
                None,
                template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
            ),
            template,
        )

    def test_unknown_or_invalid_ref_fails_closed(self):
        registry = BuiltinOutputTemplateRegistry()
        for ref in (uuid.uuid4(), None, "a1272ce0-01f0-5e6c-9706-000000000001"):
            with self.subTest(ref_type=type(ref).__name__):
                self.assertIsNone(registry.get_immutable_version(
                    object(), template_version_ref=ref))

    def test_catalog_cannot_be_mutated(self):
        registry = BuiltinOutputTemplateRegistry()
        with self.assertRaises(TypeError):
            registry._catalog[uuid.uuid4()] = registry.get_immutable_version(
                None,
                template_version_ref=BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
            )

    def test_duplicate_ids_and_mutable_or_unpublished_entries_fail_closed(self):
        valid = OutputTemplateVersion(
            BUILTIN_REQUIREMENT_DOCX_TEMPLATE_VERSION_ID,
            "DOCX",
            ("REQUIREMENT_VERSION",),
        )
        invalid = (
            (valid, valid),
            (OutputTemplateVersion(
                uuid.uuid4(), "DOCX", ("REQUIREMENT_VERSION",), immutable=False),),
            (OutputTemplateVersion(
                uuid.uuid4(), "DOCX", ("REQUIREMENT_VERSION",), published=False),),
            (OutputTemplateVersion(uuid.uuid4(), "PPTX", ("REQUIREMENT_VERSION",)),),
            (OutputTemplateVersion(uuid.uuid4(), "DOCX", ("REQUIREMENT_VERSION", "REQUIREMENT_VERSION")),),
        )
        for entries in invalid:
            with self.subTest(entries=entries):
                with self.assertRaisesRegex(ValueError, "catalog is invalid"):
                    BuiltinOutputTemplateRegistry(entries)


if __name__ == "__main__":
    unittest.main()
