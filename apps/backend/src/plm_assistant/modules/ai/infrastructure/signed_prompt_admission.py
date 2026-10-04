"""Read-only, fail-closed admission for signed PromptVersion fingerprints."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft


_FORMAT = "PLM_PROMPT_ADMISSION_V1"
_DOMAIN = b"PLM-PROMPT-ADMISSION-V1\n"
_REF = re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_TASKS = frozenset((
    "DOCUMENT_PARSE", "CAPABILITY_EXTRACT", "GAP_ANALYSIS", "SURVEY_GENERATE",
    "SURVEY_ANALYZE", "REQUIREMENT_NORMALIZE", "REQUIREMENT_MATCH",
    "SOLUTION_SUGGEST", "PROTOTYPE_GENERATE", "SOLUTION_GENERATE",
    "PLAN_GENERATE", "OUTPUT_SUMMARIZE",
))


class PromptAdmissionError(ValueError):
    """Invalid or untrusted manifest; details must not include sensitive input."""


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PromptAdmissionError("invalid Prompt admission manifest")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise PromptAdmissionError("invalid Prompt admission manifest")


def _parse_manifest(signed_manifest: bytes) -> tuple[dict[str, object], bytes, bytes]:
    if type(signed_manifest) is not bytes or not 1 <= len(signed_manifest) <= 65_536:
        raise PromptAdmissionError("invalid Prompt admission manifest")
    try:
        raw = json.loads(signed_manifest.decode("utf-8", "strict"),
                         object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise PromptAdmissionError("invalid Prompt admission manifest") from None
    if (type(raw) is not dict or set(raw) != {"format", "payload", "signature"}
            or raw["format"] != _FORMAT or type(raw["payload"]) is not dict
            or type(raw["signature"]) is not str):
        raise PromptAdmissionError("invalid Prompt admission manifest")
    payload = raw["payload"]
    if set(payload) != {"generation", "reviewer_ref", "reviewed_at", "entries"}:
        raise PromptAdmissionError("invalid Prompt admission manifest")
    if (type(payload["generation"]) is not int or not 1 <= payload["generation"] <= 2147483647
            or type(payload["reviewer_ref"]) is not str
            or _REF.fullmatch(payload["reviewer_ref"]) is None
            or type(payload["reviewed_at"]) is not str
            or not payload["reviewed_at"].endswith("Z")
            or type(payload["entries"]) is not list
            or not 1 <= len(payload["entries"]) <= 256):
        raise PromptAdmissionError("invalid Prompt admission manifest")
    try:
        reviewed = datetime.fromisoformat(payload["reviewed_at"].replace("Z", "+00:00"))
    except ValueError:
        raise PromptAdmissionError("invalid Prompt admission manifest") from None
    if reviewed.utcoffset() is None or reviewed.utcoffset().total_seconds() != 0:
        raise PromptAdmissionError("invalid Prompt admission manifest")
    keys: list[tuple[str, str, str]] = []
    for entry in payload["entries"]:
        if (type(entry) is not dict
                or set(entry) != {"prompt_template_id", "task_type", "fingerprint"}
                or type(entry["prompt_template_id"]) is not str
                or type(entry["task_type"]) is not str
                or entry["task_type"] not in _TASKS
                or type(entry["fingerprint"]) is not str
                or _HEX.fullmatch(entry["fingerprint"]) is None):
            raise PromptAdmissionError("invalid Prompt admission manifest")
        try:
            identifier = uuid.UUID(entry["prompt_template_id"])
        except ValueError:
            raise PromptAdmissionError("invalid Prompt admission manifest") from None
        if identifier.int == 0 or str(identifier) != entry["prompt_template_id"]:
            raise PromptAdmissionError("invalid Prompt admission manifest")
        keys.append((entry["prompt_template_id"], entry["task_type"], entry["fingerprint"]))
    if keys != sorted(set(keys)):
        raise PromptAdmissionError("invalid Prompt admission manifest")
    try:
        signature = base64.b64decode(raw["signature"], validate=True)
    except (ValueError, binascii.Error):
        raise PromptAdmissionError("invalid Prompt admission manifest") from None
    if len(signature) != 64:
        raise PromptAdmissionError("invalid Prompt admission manifest")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    return payload, signature, canonical


class SignedPromptAdmission:
    """Verifier only. The public key and pinned digest must come from trusted release config."""

    def __init__(self, *, public_key: bytes, signed_manifest: bytes,
                 expected_manifest_sha256: bytes) -> None:
        if (type(public_key) is not bytes or len(public_key) != 32
                or type(expected_manifest_sha256) is not bytes
                or len(expected_manifest_sha256) != 32):
            raise PromptAdmissionError("Prompt admission trust source unavailable")
        if (type(signed_manifest) is not bytes
                or not hmac.compare_digest(hashlib.sha256(signed_manifest).digest(),
                                           expected_manifest_sha256)):
            raise PromptAdmissionError("Prompt admission trust source unavailable")
        payload, signature, canonical = _parse_manifest(signed_manifest)
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature, _DOMAIN + canonical,
            )
        except (InvalidSignature, ValueError):
            raise PromptAdmissionError("Prompt admission signature invalid") from None
        self._approved = frozenset((
            entry["prompt_template_id"], entry["task_type"], entry["fingerprint"]
        ) for entry in payload["entries"])

    def approved_fingerprint(self, transaction: object, *, actor_id: uuid.UUID,
                             draft: PromptVersionDraft) -> bytes | None:
        if (transaction is None or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(draft) is not PromptVersionDraft):
            return None
        fingerprint = draft.fingerprint
        lookup = (str(draft.prompt_template_id), draft.task_type.value, fingerprint.hex())
        return fingerprint if lookup in self._approved else None
