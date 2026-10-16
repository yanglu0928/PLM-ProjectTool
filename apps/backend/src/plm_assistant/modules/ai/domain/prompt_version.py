"""Canonical, bounded PromptVersion content; semantic admission is separate."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType


_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_OBVIOUS_SECRET = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{20,}|\bk-ws-[A-Za-z0-9_.-]{20,}|"
    r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----)", re.IGNORECASE,
)
_UNSAFE_FORMAT = {"Cf", "Cs", "Co", "Cn"}


class PromptVersionError(ValueError):
    pass


def _canonical_text(value: str) -> str:
    if type(value) is not str:
        raise PromptVersionError("invalid Prompt text")
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n"))
    if (not 1 <= len(normalized) <= 65536 or not normalized.strip()
            or "\r" in normalized or _OBVIOUS_SECRET.search(normalized)):
        raise PromptVersionError("invalid Prompt text")
    if any((ord(char) < 32 and char not in "\n\t")
           or unicodedata.category(char) in _UNSAFE_FORMAT
           for char in normalized):
        raise PromptVersionError("invalid Prompt text")
    return normalized


@dataclass(frozen=True, slots=True)
class PromptVersionDraft:
    prompt_template_id: uuid.UUID
    task_type: PromptTaskType
    system_template: str = field(repr=False)
    user_template: str = field(repr=False)
    output_schema_ref: str
    schema_version: int
    rag_policy_ref: str
    provider_policy_ref: str

    def __post_init__(self) -> None:
        if (type(self.prompt_template_id) is not uuid.UUID or self.prompt_template_id.int == 0
                or type(self.task_type) is not PromptTaskType
                or any(type(value) is not str or _REF.fullmatch(value) is None
                       or _OBVIOUS_SECRET.search(value) is not None for value in (
                    self.output_schema_ref, self.rag_policy_ref, self.provider_policy_ref,
                ))
                or type(self.schema_version) is not int or not 1 <= self.schema_version <= 2147483647):
            raise PromptVersionError("invalid PromptVersion metadata")
        object.__setattr__(self, "system_template", _canonical_text(self.system_template))
        object.__setattr__(self, "user_template", _canonical_text(self.user_template))

    @property
    def system_hash(self) -> str:
        return hashlib.sha256(self.system_template.encode("utf-8")).hexdigest()

    @property
    def user_hash(self) -> str:
        return hashlib.sha256(self.user_template.encode("utf-8")).hexdigest()

    @property
    def fingerprint(self) -> bytes:
        fields = {
            "prompt_template_id": str(self.prompt_template_id),
            "task_type": self.task_type.value,
            "system_hash": self.system_hash,
            "user_hash": self.user_hash,
            "output_schema_ref": self.output_schema_ref,
            "schema_version": self.schema_version,
            "rag_policy_ref": self.rag_policy_ref,
            "provider_policy_ref": self.provider_policy_ref,
        }
        return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")).encode("utf-8")).digest()
