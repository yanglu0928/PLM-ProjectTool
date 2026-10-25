"""Non-sensitive PLT-01 value rules; policies are developer-owned, not user input."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_FORBIDDEN_KEY_PARTS = frozenset({
    "secret", "secrets", "password", "passwords", "token", "tokens",
    "credential", "credentials", "private_key", "api_key", "customer_body",
})


class ConfigurationValueError(ValueError):
    """Fixed-message rejection; never includes a submitted value."""


class ConfigurationValueType(StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    JSON = "JSON"


def _canonical_json(value: Any) -> bytes:
    try:
        serialized = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise ConfigurationValueError("configuration value is not allowed") from None
    if len(serialized) > 2048:
        raise ConfigurationValueError("configuration value is not allowed")
    return serialized


@dataclass(frozen=True, slots=True)
class ConfigurationValuePolicy:
    """An exact-value allowlist supplied by trusted deployment code."""

    config_key: str
    schema_version: int
    value_type: ConfigurationValueType
    allowed_values: tuple[Any, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.config_key, str)
            or len(self.config_key) > 64
            or _KEY_PATTERN.fullmatch(self.config_key) is None
            or _FORBIDDEN_KEY_PARTS.intersection(self.config_key.split("."))
            or type(self.schema_version) is not int
            or self.schema_version < 1
            or not isinstance(self.value_type, ConfigurationValueType)
            or not self.allowed_values
        ):
            raise ConfigurationValueError("configuration policy is invalid")
        for value in self.allowed_values:
            self._validate_shape(value)
            _canonical_json(value)

    def _validate_shape(self, value: Any) -> None:
        valid = (
            (self.value_type is ConfigurationValueType.STRING and type(value) is str)
            or (self.value_type is ConfigurationValueType.INTEGER and type(value) is int)
            or (self.value_type is ConfigurationValueType.BOOLEAN and type(value) is bool)
            or (self.value_type is ConfigurationValueType.JSON and type(value) in (dict, list))
        )
        if not valid:
            raise ConfigurationValueError("configuration value is not allowed")

    def fingerprint(self, *, schema_version: int, value: Any) -> bytes:
        if type(schema_version) is not int or schema_version != self.schema_version:
            raise ConfigurationValueError("configuration schema version is not allowed")
        self._validate_shape(value)
        canonical = _canonical_json(value)
        if canonical not in {_canonical_json(item) for item in self.allowed_values}:
            raise ConfigurationValueError("configuration value is not allowed")
        envelope = (
            b"PLT-01\0" + str(schema_version).encode("ascii") + b"\0"
            + self.value_type.value.encode("ascii") + b"\0" + canonical
        )
        return hashlib.sha256(envelope).digest()
