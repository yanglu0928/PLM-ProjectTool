"""Fail-closed Windows key composition for Prototype read cursors."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.prototype.api.cursors import (
    PrototypeCursorCodec,
    PrototypePackageCursorCodec,
    PrototypeTemplateCursorCodec,
    PrototypeVersionCursorCodec,
    RequirementPrototypeLinkCursorCodec,
)


PROTOTYPE_PACKAGE_CURSOR_KEY_REF = "prototype-package-cursor-v1"
PROTOTYPE_CURSOR_KEY_REF = "prototype-list-cursor-v1"
PROTOTYPE_VERSION_CURSOR_KEY_REF = "prototype-version-cursor-v1"
PROTOTYPE_TEMPLATE_CURSOR_KEY_REF = "prototype-template-cursor-v1"
PROTOTYPE_LINK_CURSOR_KEY_REF = "prototype-requirement-link-cursor-v1"

PROTOTYPE_CURSOR_KEY_REFS = (
    PROTOTYPE_PACKAGE_CURSOR_KEY_REF,
    PROTOTYPE_CURSOR_KEY_REF,
    PROTOTYPE_VERSION_CURSOR_KEY_REF,
    PROTOTYPE_TEMPLATE_CURSOR_KEY_REF,
    PROTOTYPE_LINK_CURSOR_KEY_REF,
)


class PrototypeCursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionPrototypeCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Prototype cursor keys unavailable")


@dataclass(frozen=True, slots=True)
class WindowsPrototypeCursorCodecs:
    package: PrototypePackageCursorCodec
    prototype: PrototypeCursorCodec
    version: PrototypeVersionCursorCodec
    template: PrototypeTemplateCursorCodec
    link: RequirementPrototypeLinkCursorCodec

    def __post_init__(self) -> None:
        expected = (
            (self.package, PrototypePackageCursorCodec),
            (self.prototype, PrototypeCursorCodec),
            (self.version, PrototypeVersionCursorCodec),
            (self.template, PrototypeTemplateCursorCodec),
            (self.link, RequirementPrototypeLinkCursorCodec),
        )
        if any(type(value) is not kind for value, kind in expected):
            raise ProductionPrototypeCursorStartupError()


def create_windows_prototype_cursor_codecs(
    *, resolver: PrototypeCursorKeyResolverPort | None = None,
) -> WindowsPrototypeCursorCodecs:
    """Resolve five dedicated recoverable keys; never generate or fall back."""
    try:
        source = resolver if resolver is not None else WindowsSecretKeyProvider()
        keys = tuple(source.resolve_key(key_ref) for key_ref in PROTOTYPE_CURSOR_KEY_REFS)
        if any(type(key) is not bytes or len(key) != 32 for key in keys):
            raise ValueError("invalid Prototype cursor key")
        if any(hmac.compare_digest(left, right)
               for index, left in enumerate(keys)
               for right in keys[index + 1:]):
            raise ValueError("Prototype cursor keys must be independent")
        return WindowsPrototypeCursorCodecs(
            PrototypePackageCursorCodec(keys[0]),
            PrototypeCursorCodec(keys[1]),
            PrototypeVersionCursorCodec(keys[2]),
            PrototypeTemplateCursorCodec(keys[3]),
            RequirementPrototypeLinkCursorCodec(keys[4]),
        )
    except Exception:
        raise ProductionPrototypeCursorStartupError() from None
