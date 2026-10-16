"""Developer-only release metadata builder for a reviewed signed Prompt manifest."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from plm_assistant.modules.ai.infrastructure.signed_prompt_admission import (
    SignedPromptAdmission, _parse_manifest,
)


_ROOT = Path(__file__).resolve().parents[2]
_PUBLIC_SCHEMA = "plm.prompt-admission-public-key.v1"
_RELEASE_SCHEMA = "plm.prompt-admission-release.v1"
_KEY_REF = "plm-prompt-admission-release-v1"


class PromptReleaseError(ValueError):
    def __init__(self) -> None:
        super().__init__("Prompt admission release preparation failed")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PromptReleaseError()
        result[key] = value
    return result


def prepare_release(public_manifest: bytes, signed_manifest: bytes) -> bytes:
    """Derive release pin only after the signed file verifies with this exact key."""
    try:
        if (type(public_manifest) is not bytes or not 1 <= len(public_manifest) <= 512
                or type(signed_manifest) is not bytes):
            raise PromptReleaseError()
        value = json.loads(public_manifest.decode("utf-8", "strict"),
                           object_pairs_hook=_unique_pairs)
        if (type(value) is not dict
                or set(value) != {"schema_version", "key_ref", "public_key"}
                or value["schema_version"] != _PUBLIC_SCHEMA
                or value["key_ref"] != _KEY_REF
                or type(value["public_key"]) is not str):
            raise PromptReleaseError()
        public = base64.b64decode(value["public_key"], validate=True)
        if len(public) != 32 or base64.b64encode(public).decode("ascii") != value["public_key"]:
            raise PromptReleaseError()
        digest = hashlib.sha256(signed_manifest).digest()
        SignedPromptAdmission(public_key=public, signed_manifest=signed_manifest,
                              expected_manifest_sha256=digest)
        payload, _, _ = _parse_manifest(signed_manifest)
        release = {"schema_version": _RELEASE_SCHEMA, "key_ref": _KEY_REF,
                   "public_key": value["public_key"],
                   "manifest_sha256": digest.hex(), "generation": payload["generation"]}
        return json.dumps(release, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    except Exception:
        raise PromptReleaseError() from None


def _read(path: Path, limit: int) -> bytes:
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= limit):
        raise PromptReleaseError()
    return path.read_bytes()


def main() -> int:
    if len(sys.argv) != 5 or sys.argv[1] != "prepare":
        print("Usage: prepare ABS_PUBLIC_JSON ABS_SIGNED_JSON ABS_OUTPUT_RELEASE_JSON", file=sys.stderr)
        return 2
    try:
        public_path, signed_path, output_path = map(Path, sys.argv[2:5])
        if (not output_path.is_absolute() or output_path.resolve().is_relative_to(_ROOT)
                or output_path.exists() or output_path.parent.is_symlink()
                or not output_path.parent.is_dir()):
            raise PromptReleaseError()
        public = _read(public_path, 512)
        signed = _read(signed_path, 65_536)
        release = prepare_release(public, signed)
        with output_path.open("xb") as file:
            file.write(release)
            file.flush()
            os.fsync(file.fileno())
        print(f"Release metadata SHA-256: {hashlib.sha256(release).hexdigest()}")
        print("Verify signed content review and trusted package integrity before distribution.")
        return 0
    except Exception:
        print("Prompt release preparation failed; no input content was printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
