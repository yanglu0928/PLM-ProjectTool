"""Composition adapter from the Plugin public owner projection to Output."""
from __future__ import annotations

from plm_assistant.modules.output.application.resolve_context import (
    PluginOperationCapability,
)
from plm_assistant.modules.plugin.application.operation_capability import (
    PluginOperationCapabilityReader,
)


class PluginOperationRegistryAdapter:
    """Expose only the capability fields required by Output's resolver port."""

    def __init__(self, reader: PluginOperationCapabilityReader) -> None:
        if reader is None:
            raise ValueError("Plugin operation capability reader is required")
        self._reader = reader

    def get_operation(
        self, transaction: object, *, operation_id: str,
    ) -> PluginOperationCapability | None:
        try:
            value = self._reader.get_operation(
                transaction, operation_id=operation_id,
            )
        except Exception:
            return None
        if value is None:
            return None
        return PluginOperationCapability(
            operation_id=value.operation_id,
            output_types=value.output_types,
            enabled=value.enabled,
            trusted=value.trusted,
        )
