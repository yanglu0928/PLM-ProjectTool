from __future__ import annotations

import unittest

from plm_assistant.modules.output.application.resolve_context import (
    PluginOperationCapability,
)
from plm_assistant.modules.output.infrastructure.plugin_operation_registry_adapter import (
    PluginOperationRegistryAdapter,
)
from plm_assistant.modules.plugin.application.operation_capability import (
    PluginOperationCapabilityReader,
    PluginOperationCapabilityView,
)


class Repository:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.transaction = None

    def get_operation(self, transaction, *, operation_id):
        self.transaction = transaction
        if self.error:
            raise self.error
        if self.value is None or self.value.operation_id != operation_id:
            return None
        return self.value


class PluginOperationCapabilityAdapterTests(unittest.TestCase):
    def test_maps_only_the_minimal_capability_projection(self):
        transaction = object()
        repository = Repository(PluginOperationCapabilityView(
            "word.generate", ("DOCX",), True, True,
        ))
        adapter = PluginOperationRegistryAdapter(
            PluginOperationCapabilityReader(repository),
        )
        result = adapter.get_operation(transaction, operation_id="word.generate")
        self.assertEqual(result, PluginOperationCapability(
            "word.generate", ("DOCX",), enabled=True, trusted=True,
        ))
        self.assertIs(repository.transaction, transaction)

    def test_missing_or_malformed_owner_facts_fail_closed(self):
        for value in (
            None,
            PluginOperationCapabilityView("other.operation", ("DOCX",), True, True),
            PluginOperationCapabilityView("word.generate", ("../private",), True, True),
        ):
            adapter = PluginOperationRegistryAdapter(
                PluginOperationCapabilityReader(Repository(value)),
            )
            with self.subTest(value=value):
                self.assertIsNone(adapter.get_operation(
                    object(), operation_id="word.generate",
                ))

    def test_owner_exception_and_invalid_operation_fail_closed(self):
        reader = PluginOperationCapabilityReader(Repository(error=RuntimeError("db")))
        adapter = PluginOperationRegistryAdapter(reader)
        self.assertIsNone(adapter.get_operation(object(), operation_id="word.generate"))
        self.assertIsNone(adapter.get_operation(object(), operation_id="../secret"))

    def test_disabled_or_untrusted_projection_is_preserved_for_resolver(self):
        for enabled, trusted in ((False, True), (True, False)):
            adapter = PluginOperationRegistryAdapter(
                PluginOperationCapabilityReader(Repository(
                    PluginOperationCapabilityView(
                        "word.generate", ("DOCX",), enabled, trusted,
                    ),
                )),
            )
            self.assertEqual(adapter.get_operation(
                object(), operation_id="word.generate",
            ), PluginOperationCapability(
                "word.generate", ("DOCX",), enabled=enabled, trusted=trusted,
            ))


if __name__ == "__main__":
    unittest.main()
