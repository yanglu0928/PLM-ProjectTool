from __future__ import annotations

import ipaddress
import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


_MAX_BOOTSTRAP_BYTES = 65_536


class BootstrapConfigurationError(ValueError):
    """A fixed-message failure that does not disclose config values or paths."""


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootstrapSettings(BaseSettings):
    """Non-secret, process-local deployment settings only."""

    model_config = SettingsConfigDict(
        env_prefix="PLM_",
        extra="forbid",
        frozen=True,
        case_sensitive=False,
        env_file=None,
    )

    bind_host: str = "127.0.0.1"
    bind_port: int = Field(default=8000, ge=1, le=65_535)
    data_root: Path
    log_level: LogLevel = LogLevel.INFO

    @field_validator("bind_host")
    @classmethod
    def validate_bind_host(cls, value: str) -> str:
        ipaddress.ip_address(value)
        return value

    @field_validator("data_root")
    @classmethod
    def validate_data_root(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("data root must be absolute")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # No implicit file Secret source. Dotenv is only enabled by the explicit
        # development_env_file argument of load_bootstrap_settings().
        return env_settings, dotenv_settings, init_settings


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _mapping_without_duplicates(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in values:
            raise BootstrapConfigurationError("invalid bootstrap configuration")
        values[key] = loader.construct_object(value_node, deep=True)
    return values


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_without_duplicates
)


def _read_bounded_file(path: Path) -> str:
    with path.open("rb") as stream:
        content = stream.read(_MAX_BOOTSTRAP_BYTES + 1)
    if len(content) > _MAX_BOOTSTRAP_BYTES:
        raise BootstrapConfigurationError("invalid bootstrap configuration")
    return content.decode("utf-8-sig")


def load_bootstrap_settings(
    yaml_file: Path,
    *,
    development_env_file: Path | None = None,
) -> BootstrapSettings:
    """Load allowlisted YAML, then explicit dev dotenv, then PLM_ environment."""

    try:
        text = _read_bounded_file(yaml_file)
        raw = yaml.load(text, Loader=_UniqueKeySafeLoader)
        if not isinstance(raw, dict):
            raise BootstrapConfigurationError("invalid bootstrap configuration")

        allowed = set(BootstrapSettings.model_fields)
        prefixed = {
            name[4:].lower()
            for name in os.environ
            if name.upper().startswith("PLM_")
        }
        if not prefixed.issubset(allowed):
            raise BootstrapConfigurationError("invalid bootstrap configuration")

        if development_env_file is not None:
            _read_bounded_file(development_env_file)
        return BootstrapSettings(
            _env_file=development_env_file,
            **raw,
        )
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, ValueError) as exc:
        del exc
        raise BootstrapConfigurationError("invalid bootstrap configuration") from None
