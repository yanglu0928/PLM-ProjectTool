"""Developer-only Prompt admission key ceremony; not part of the customer wheel."""

from __future__ import annotations

import base64
import getpass
import json
import os
import secrets
import sys
import warnings
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


_PRIVATE_DIR = Path(__file__).resolve().parent / "private"
PRIVATE_PATH = _PRIVATE_DIR / "prompt-admission-signing-v1.pem"
PUBLIC_PATH = _PRIVATE_DIR / "prompt-admission-public-v1.json"
_SCHEMA = "plm.prompt-admission-public-key.v1"
_REF = "plm-prompt-admission-release-v1"


class PromptKeyCeremonyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Prompt admission key ceremony unavailable")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PromptKeyCeremonyError()
        result[key] = value
    return result


def _password(value: bytearray) -> bytes:
    if type(value) is not bytearray or not 24 <= len(value) <= 1024 or b"\x00" in value:
        raise PromptKeyCeremonyError()
    return bytes(value)


def create_pair(private_path: Path, public_path: Path, passphrase: bytearray) -> None:
    """Create a fresh independent identity without overwriting either artifact."""
    try:
        password = _password(passphrase)
        if (not private_path.is_absolute() or not public_path.is_absolute()
                or private_path == public_path or private_path.exists() or public_path.exists()
                or private_path.parent.is_symlink() or public_path.parent.is_symlink()
                or not private_path.parent.is_dir() or not public_path.parent.is_dir()):
            raise PromptKeyCeremonyError()
        private = Ed25519PrivateKey.generate()
        encrypted = private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password),
        )
        public = private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        manifest = json.dumps({"schema_version": _SCHEMA, "key_ref": _REF,
                               "public_key": base64.b64encode(public).decode("ascii")},
                              sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
        with private_path.open("xb") as file:
            file.write(encrypted)
            file.flush()
            os.fsync(file.fileno())
        with public_path.open("xb") as file:
            file.write(manifest)
            file.flush()
            os.fsync(file.fileno())
        verify_pair(private_path, public_path, bytearray(password))
    except Exception:
        raise PromptKeyCeremonyError() from None
    finally:
        if type(passphrase) is bytearray:
            passphrase[:] = b"\x00" * len(passphrase)


def verify_pair(private_path: Path, public_path: Path, passphrase: bytearray) -> None:
    """Verify original or offline private copy against the public manifest."""
    try:
        password = _password(passphrase)
        if (not private_path.is_absolute() or not public_path.is_absolute()
                or private_path.is_symlink() or public_path.is_symlink()
                or not private_path.is_file() or not public_path.is_file()
                or not 1 <= private_path.stat().st_size <= 8192
                or not 1 <= public_path.stat().st_size <= 512):
            raise PromptKeyCeremonyError()
        private = serialization.load_pem_private_key(private_path.read_bytes(), password)
        if not isinstance(private, Ed25519PrivateKey):
            raise PromptKeyCeremonyError()
        value = json.loads(public_path.read_text(encoding="ascii"),
                           object_pairs_hook=_unique_pairs)
        if (type(value) is not dict
                or set(value) != {"schema_version", "key_ref", "public_key"}
                or value["schema_version"] != _SCHEMA or value["key_ref"] != _REF
                or type(value["public_key"]) is not str):
            raise PromptKeyCeremonyError()
        public = base64.b64decode(value["public_key"], validate=True)
        if len(public) != 32 or base64.b64encode(public).decode("ascii") != value["public_key"]:
            raise PromptKeyCeremonyError()
        challenge = secrets.token_bytes(32)
        Ed25519PublicKey.from_public_bytes(public).verify(private.sign(challenge), challenge)
    except Exception:
        raise PromptKeyCeremonyError() from None
    finally:
        if type(passphrase) is bytearray:
            passphrase[:] = b"\x00" * len(passphrase)


def main() -> int:
    if (not sys.stdin.isatty() or len(sys.argv) not in (2, 3)
            or sys.argv[1] not in {"create", "verify"}
            or (sys.argv[1] == "create" and len(sys.argv) != 2)):
        print("Interactive create|verify [absolute-private-copy] required.", file=sys.stderr)
        return 2
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            first = getpass.getpass("Prompt signing-key passphrase (hidden): ")
            if sys.argv[1] == "create":
                second = getpass.getpass("Confirm passphrase (hidden): ")
                if first != second:
                    raise PromptKeyCeremonyError()
        password = bytearray(first.encode("utf-8", errors="strict"))
        if sys.argv[1] == "create":
            _PRIVATE_DIR.mkdir(exist_ok=True)
            create_pair(PRIVATE_PATH, PUBLIC_PATH, password)
        else:
            source = Path(sys.argv[2]) if len(sys.argv) == 3 else PRIVATE_PATH
            verify_pair(source, PUBLIC_PATH, password)
        print("Prompt key verified; keep encrypted private key and passphrase backed up separately.")
        return 0
    except Exception:
        print("Prompt key ceremony failed; no key material was printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
