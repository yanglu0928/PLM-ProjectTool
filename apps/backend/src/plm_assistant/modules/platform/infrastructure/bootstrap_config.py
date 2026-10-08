from __future__ import annotations

import ipaddress
import os
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

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
    trusted_origins: tuple[str, ...] = ()
    selected_mac: str | None = None
    password_kdf_slots: int = Field(default=4, ge=1, le=16)
    api_database_pool_profile: Literal["DEFAULT", "TWENTY_FIXED"] = "DEFAULT"
    parser_ocr_detection_model_dir: Path | None = None
    parser_ocr_recognition_model_dir: Path | None = None
    parser_ocr_model_fingerprint: str | None = None
    ai_probe_policies: tuple[dict[str, str], ...] = ()
    ai_execution_policies: tuple[dict[str, Any], ...] = ()
    ai_egress_policies: tuple[dict[str, Any], ...] = ()
    ai_task_policies: tuple[dict[str, Any], ...] = ()
    rag_retrieval_policies: tuple[dict[str, str], ...] = ()

    @field_validator("rag_retrieval_policies", mode="before")
    @classmethod
    def validate_rag_retrieval_policies(
        cls, value: Any,
    ) -> tuple[dict[str, str], ...]:
        """Accept only the first zero-egress retrieval strategy.

        This setting is an explicit deployment opt-in.  Query key material is
        deliberately absent and must be resolved from the process account's
        dedicated Windows vault entry by the API and Worker composition roots.
        """
        fields = frozenset({
            "reference", "scope", "rerank_policy_ref", "context_policy_ref",
        })
        expected = {
            "reference": "fts.project.v1",
            "scope": "PROJECT",
            "rerank_policy_ref": "none.v1",
            "context_policy_ref": "project-documents.v1",
        }
        if (type(value) not in (tuple, list) or len(value) > 1
                or any(type(item) is not dict or set(item) != fields
                       or any(type(field) is not str for field in item.values())
                       or item != expected for item in value)):
            raise ValueError("invalid RAG Retrieval policy configuration")
        return tuple(dict(item) for item in value)

    @field_validator("ai_probe_policies", mode="before")
    @classmethod
    def validate_ai_probe_policies(cls, value: Any) -> tuple[dict[str, str], ...]:
        fields = frozenset({"reference", "kind", "endpoint_url", "model_key",
                            "data_region", "egress_class"})
        if (type(value) not in (tuple, list) or len(value) > 16
                or any(type(item) is not dict or set(item) != fields
                       or any(type(key) is not str or type(field) is not str
                              for key, field in item.items()) for item in value)):
            raise ValueError("invalid AI probe policy configuration")
        references = [item["reference"] for item in value]
        if len(set(references)) != len(references):
            raise ValueError("invalid AI probe policy configuration")
        return tuple(dict(item) for item in value)

    @field_validator("ai_execution_policies", mode="before")
    @classmethod
    def validate_ai_execution_policies(
        cls, value: Any,
    ) -> tuple[dict[str, Any], ...]:
        fields = frozenset({
            "reference", "kind", "endpoint_url", "data_region",
            "egress_class", "allowed_model_keys", "max_response_bytes",
            "connect_timeout_seconds", "read_timeout_seconds",
            "total_timeout_seconds",
        })
        string_fields = (
            "reference", "kind", "endpoint_url", "data_region",
            "egress_class",
        )
        integer_bounds = {
            "max_response_bytes": (1, 100_000_000),
            "connect_timeout_seconds": (1, 120),
            "read_timeout_seconds": (1, 120),
            "total_timeout_seconds": (1, 120),
        }
        if type(value) not in (tuple, list) or len(value) > 16:
            raise ValueError("invalid AI execution policy configuration")
        normalized: list[dict[str, Any]] = []
        for item in value:
            if (type(item) is not dict or set(item) != fields
                    or any(type(item[name]) is not str for name in string_fields)
                    or type(item["allowed_model_keys"]) not in (tuple, list)
                    or not 1 <= len(item["allowed_model_keys"]) <= 64
                    or len(set(item["allowed_model_keys"]))
                    != len(item["allowed_model_keys"])
                    or any(type(model) is not str
                           for model in item["allowed_model_keys"])
                    or any(type(item[name]) is not int
                           or not low <= item[name] <= high
                           for name, (low, high) in integer_bounds.items())):
                raise ValueError("invalid AI execution policy configuration")
            normalized.append({
                **item,
                "allowed_model_keys": tuple(item["allowed_model_keys"]),
            })
        references = [item["reference"] for item in normalized]
        if len(set(references)) != len(references):
            raise ValueError("invalid AI execution policy configuration")
        return tuple(normalized)

    @field_validator("ai_egress_policies", mode="before")
    @classmethod
    def validate_ai_egress_policies(cls, value: Any) -> tuple[dict[str, Any], ...]:
        fields = frozenset({
            "reference", "operation_types", "data_categories", "ttl_minutes",
            "max_record_count", "max_payload_bytes", "max_input_tokens",
            "max_retry_attempts", "risk_codes", "approval_roles", "data_regions",
        })
        list_fields = (
            "operation_types", "data_categories", "risk_codes", "approval_roles",
            "data_regions",
        )
        bounds = {
            "ttl_minutes": (1, 1_440),
            "max_record_count": (0, 1_000_000_000),
            "max_payload_bytes": (1, 1_073_741_824),
            "max_input_tokens": (1, 1_048_576),
            "max_retry_attempts": (1, 10),
        }
        if type(value) not in (tuple, list) or len(value) > 16:
            raise ValueError("invalid AI Egress policy configuration")
        normalized: list[dict[str, Any]] = []
        for item in value:
            if (type(item) is not dict or set(item) != fields
                    or type(item["reference"]) is not str):
                raise ValueError("invalid AI Egress policy configuration")
            for name in list_fields:
                field = item[name]
                if (type(field) not in (tuple, list) or not 1 <= len(field) <= 64
                        or len(set(field)) != len(field)
                        or any(type(entry) is not str for entry in field)):
                    raise ValueError("invalid AI Egress policy configuration")
            if any(type(item[name]) is not int or not low <= item[name] <= high
                   for name, (low, high) in bounds.items()):
                raise ValueError("invalid AI Egress policy configuration")
            normalized.append({
                **item,
                **{name: tuple(item[name]) for name in list_fields},
            })
        references = [item["reference"] for item in normalized]
        if len(set(references)) != len(references):
            raise ValueError("invalid AI Egress policy configuration")
        return tuple(normalized)

    @field_validator("ai_task_policies", mode="before")
    @classmethod
    def validate_ai_task_policies(cls, value: Any) -> tuple[dict[str, Any], ...]:
        fields = frozenset({
            "reference", "policy_version", "task_type", "prompt_template_id",
            "purpose_ref", "output_schema_ref", "context_policy_ref",
            "parameter_fields",
        })
        parameter_fields = frozenset({
            "name", "value_type", "required", "max_length", "minimum",
            "maximum", "allowed_values",
        })
        if type(value) not in (tuple, list) or len(value) > 64:
            raise ValueError("invalid AI Task policy configuration")
        normalized: list[dict[str, Any]] = []
        for item in value:
            if (type(item) is not dict or set(item) != fields
                    or any(type(item[name]) is not str for name in (
                        "reference", "task_type", "prompt_template_id", "purpose_ref",
                        "output_schema_ref", "context_policy_ref",
                    ))
                    or type(item["policy_version"]) is not int
                    or type(item["parameter_fields"]) not in (tuple, list)
                    or len(item["parameter_fields"]) > 16):
                raise ValueError("invalid AI Task policy configuration")
            parameters: list[dict[str, Any]] = []
            for parameter in item["parameter_fields"]:
                if (type(parameter) is not dict or set(parameter) != parameter_fields
                        or type(parameter["name"]) is not str
                        or type(parameter["value_type"]) is not str
                        or type(parameter["required"]) is not bool
                        or any(parameter[name] is not None
                               and type(parameter[name]) is not int
                               for name in ("max_length", "minimum", "maximum"))
                        or type(parameter["allowed_values"]) not in (tuple, list)
                        or len(parameter["allowed_values"]) > 64
                        or any(type(entry) is not str
                               for entry in parameter["allowed_values"])):
                    raise ValueError("invalid AI Task policy configuration")
                parameters.append({
                    **parameter,
                    "allowed_values": tuple(parameter["allowed_values"]),
                })
            normalized.append({**item, "parameter_fields": tuple(parameters)})
        references = [item["reference"] for item in normalized]
        if len(set(references)) != len(references):
            raise ValueError("invalid AI Task policy configuration")
        return tuple(normalized)

    @field_validator("parser_ocr_detection_model_dir", "parser_ocr_recognition_model_dir")
    @classmethod
    def validate_parser_model_dir(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("absolute Parser OCR model directory required")
        return value

    @field_validator("parser_ocr_model_fingerprint")
    @classmethod
    def validate_parser_model_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or
                any(char not in "0123456789abcdef" for char in value)):
            raise ValueError("invalid Parser OCR fingerprint")
        return value

    @field_validator("password_kdf_slots", mode="before")
    @classmethod
    def validate_password_kdf_slots(cls, value: Any) -> int:
        if type(value) is str and value in tuple(str(i) for i in range(1, 17)):
            return int(value)
        if type(value) is int and 1 <= value <= 16:
            return value
        raise ValueError("invalid password capacity configuration")

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

    @field_validator("trusted_origins")
    @classmethod
    def validate_trusted_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        # The Auth origin policy performs the final URL/Host validation when
        # the login router is assembled. Bootstrap only accepts bounded input.
        if len(value) > 16 or any(not origin or len(origin) > 256 for origin in value):
            raise ValueError("invalid trusted origin configuration")
        return value

    @field_validator("selected_mac")
    @classmethod
    def validate_selected_mac(cls, value: str | None) -> str | None:
        # Non-secret operator choice. The License adapter verifies local presence.
        if value is not None and (not value.strip() or len(value) > 32):
            raise ValueError("invalid selected MAC configuration")
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
