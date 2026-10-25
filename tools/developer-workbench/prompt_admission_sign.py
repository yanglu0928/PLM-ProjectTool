"""Offline Prompt admission signer. Never package this developer-workbench tool."""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import sys
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import (
    PromptAdmissionError, SignedPromptAdmission, _parse_manifest,
)


_ROOT = Path(__file__).resolve().parents[2]
_DOMAIN = b"PLM-PROMPT-ADMISSION-V1\n"
_DRAFT_KEYS = {"prompt_template_id", "task_type", "system_template", "user_template",
               "output_schema_ref", "schema_version", "rag_policy_ref", "provider_policy_ref"}


class PromptSigningError(ValueError):
    def __init__(self) -> None:
        super().__init__("Prompt admission signing failed")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PromptSigningError()
        result[key] = value
    return result


def prepare_review(candidate: bytes, *, reviewer_ref: str, generation: int,
                   reviewed_at: str) -> tuple[dict[str, object], str]:
    """Compute version fingerprints from full candidate content, not supplied hashes."""
    try:
        if type(candidate) is not bytes or not 1 <= len(candidate) <= 1_048_576:
            raise PromptSigningError()
        raw = json.loads(candidate.decode("utf-8", "strict"),
                         object_pairs_hook=_unique_pairs)
        if type(raw) is not dict or set(raw) != {"drafts"} or type(raw["drafts"]) is not list:
            raise PromptSigningError()
        if not 1 <= len(raw["drafts"]) <= 256:
            raise PromptSigningError()
        entries = []
        for item in raw["drafts"]:
            if type(item) is not dict or set(item) != _DRAFT_KEYS:
                raise PromptSigningError()
            draft = PromptVersionDraft(
                prompt_template_id=uuid.UUID(item["prompt_template_id"]),
                task_type=PromptTaskType(item["task_type"]),
                system_template=item["system_template"],
                user_template=item["user_template"],
                output_schema_ref=item["output_schema_ref"],
                schema_version=item["schema_version"],
                rag_policy_ref=item["rag_policy_ref"],
                provider_policy_ref=item["provider_policy_ref"],
            )
            entries.append({"prompt_template_id": str(draft.prompt_template_id),
                            "task_type": draft.task_type.value,
                            "fingerprint": draft.fingerprint.hex()})
        entries.sort(key=lambda item: (item["prompt_template_id"], item["task_type"],
                                       item["fingerprint"]))
        payload = {"generation": generation, "reviewer_ref": reviewer_ref,
                   "reviewed_at": reviewed_at, "entries": entries}
        # Reuse the runtime's exact schema validation before any signing operation.
        unsigned = json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                               "signature": base64.b64encode(bytes(64)).decode("ascii")},
                              sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        _parse_manifest(unsigned)
        digest = hashlib.sha256(candidate).hexdigest()
        return payload, digest
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError, UnicodeError,
            json.JSONDecodeError, PromptAdmissionError):
        raise PromptSigningError() from None


def sign_reviewed_candidate(candidate: bytes, *, private_pem: bytes,
                            passphrase: bytearray, reviewer_ref: str,
                            generation: int, reviewed_at: str,
                            confirmed_candidate_sha256: str) -> bytes:
    """Sign only after the operator confirms the exact source file digest."""
    try:
        payload, candidate_digest = prepare_review(
            candidate, reviewer_ref=reviewer_ref, generation=generation,
            reviewed_at=reviewed_at,
        )
        if (type(confirmed_candidate_sha256) is not str
                or confirmed_candidate_sha256 != candidate_digest
                or type(private_pem) is not bytes or not 1 <= len(private_pem) <= 8192
                or type(passphrase) is not bytearray or not 24 <= len(passphrase) <= 1024):
            raise PromptSigningError()
        private = serialization.load_pem_private_key(private_pem, password=bytes(passphrase))
        if not isinstance(private, Ed25519PrivateKey):
            raise PromptSigningError()
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        signature = private.sign(_DOMAIN + canonical)
        document = json.dumps({"format": "PLM_PROMPT_ADMISSION_V1", "payload": payload,
                               "signature": base64.b64encode(signature).decode("ascii")},
                              sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        public = private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        SignedPromptAdmission(public_key=public, signed_manifest=document,
                              expected_manifest_sha256=hashlib.sha256(document).digest())
        return document
    except Exception:
        raise PromptSigningError() from None
    finally:
        if type(passphrase) is bytearray:
            passphrase[:] = b"\x00" * len(passphrase)


def _safe_source(path: Path, max_size: int) -> bytes:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= max_size):
        raise PromptSigningError()
    return path.read_bytes()


def main() -> int:
    if not sys.stdin.isatty() or len(sys.argv) != 7 or sys.argv[1] != "sign":
        print("Interactive use: sign ABS_CANDIDATE_JSON ABS_PRIVATE_PEM ABS_OUTPUT_JSON REVIEWER_REF GENERATION", file=sys.stderr)
        return 2
    try:
        candidate_path, private_path, output_path = map(Path, sys.argv[2:5])
        reviewer_ref = sys.argv[5]
        generation = int(sys.argv[6])
        if (not candidate_path.is_absolute() or candidate_path.resolve().is_relative_to(_ROOT)
                or not output_path.is_absolute() or output_path.resolve().is_relative_to(_ROOT)
                or output_path.exists() or output_path.parent.is_symlink()
                or not output_path.parent.is_dir()):
            raise PromptSigningError()
        candidate = _safe_source(candidate_path, 1_048_576)
        private_pem = _safe_source(private_path, 8192)
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        payload, candidate_digest = prepare_review(
            candidate, reviewer_ref=reviewer_ref, generation=generation,
            reviewed_at=reviewed_at,
        )
        print(f"Review the exact candidate file outside Git: {candidate_path}")
        print(f"Candidate SHA-256: {candidate_digest}; entries: {len(payload['entries'])}")
        print("Confirm after checking content for secrets, customer copies, Golden answers, and Evidence/Review bypasses.")
        confirmation = input("Type the full candidate SHA-256 to sign: ").strip()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = bytearray(getpass.getpass("Encrypted signing-key passphrase (hidden): ").encode("utf-8"))
        document = sign_reviewed_candidate(
            candidate, private_pem=private_pem, passphrase=password,
            reviewer_ref=reviewer_ref, generation=generation,
            reviewed_at=reviewed_at, confirmed_candidate_sha256=confirmation,
        )
        with output_path.open("xb") as file:
            file.write(document)
            file.flush()
            os.fsync(file.fileno())
        print(f"Signed manifest SHA-256: {hashlib.sha256(document).hexdigest()}")
        print("Signing alone does not establish semantic review or production trust.")
        return 0
    except Exception:
        print("Prompt admission signing failed; no content or key was printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
