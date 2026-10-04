"""Fail-closed Prompt admission trust loaded only from installed package resources."""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import Callable
from importlib import resources

from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import (
    SignedPromptAdmission, _parse_manifest,
)


_SCHEMA = "plm.prompt-admission-release.v1"
_KEY_REF = "plm-prompt-admission-release-v1"
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ROOT = "plm_assistant.modules.ai"


class PackagedPromptAdmissionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("packaged Prompt admission trust unavailable")


def _read_release() -> bytes:
    return (resources.files(_ROOT) / "trust/prompt_admission_release.json").read_bytes()


def _read_signed_manifest() -> bytes:
    return (resources.files(_ROOT) / "trust/prompt_admission_signed.json").read_bytes()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PackagedPromptAdmissionError()
        result[key] = value
    return result


class PackagedPromptAdmission:
    """Immutable admission source; no request/environment key or hash override."""

    def __init__(self, *, read_release: Callable[[], bytes] = _read_release,
                 read_signed_manifest: Callable[[], bytes] = _read_signed_manifest) -> None:
        try:
            raw = read_release()
            signed = read_signed_manifest()
            if type(raw) is not bytes or not 1 <= len(raw) <= 512 or type(signed) is not bytes:
                raise PackagedPromptAdmissionError()
            value = json.loads(raw.decode("utf-8", "strict"),
                               object_pairs_hook=_unique_pairs)
            if (type(value) is not dict
                    or set(value) != {"schema_version", "key_ref", "public_key",
                                      "manifest_sha256", "generation"}
                    or value["schema_version"] != _SCHEMA
                    or value["key_ref"] != _KEY_REF
                    or type(value["public_key"]) is not str
                    or type(value["manifest_sha256"]) is not str
                    or _HEX.fullmatch(value["manifest_sha256"]) is None
                    or type(value["generation"]) is not int
                    or not 1 <= value["generation"] <= 2147483647):
                raise PackagedPromptAdmissionError()
            public = base64.b64decode(value["public_key"], validate=True)
            if len(public) != 32 or base64.b64encode(public).decode("ascii") != value["public_key"]:
                raise PackagedPromptAdmissionError()
            digest = bytes.fromhex(value["manifest_sha256"])
            admission = SignedPromptAdmission(
                public_key=public, signed_manifest=signed,
                expected_manifest_sha256=digest,
            )
            payload, _, _ = _parse_manifest(signed)
            if payload["generation"] != value["generation"]:
                raise PackagedPromptAdmissionError()
            self._admission = admission
        except Exception:
            raise PackagedPromptAdmissionError() from None

    def approved_fingerprint(self, transaction: object, *, actor_id: uuid.UUID,
                             draft: PromptVersionDraft) -> bytes | None:
        return self._admission.approved_fingerprint(
            transaction, actor_id=actor_id, draft=draft,
        )
