"""Developer-only Plugin Ed25519 publisher key ceremony.

This tool is not part of the customer application. Real key ceremonies must be
performed interactively in the protected Developer Workbench and backed up
offline; hosted tests use only temporary synthetic keys.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import re
import secrets
import sys
import warnings
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_PATH = Path(__file__).resolve().parent / "private" / "plugin-signing-v1.pem"
PUBLIC_PATH = (
    _ROOT / "apps/backend/src/plm_assistant/modules/plugin/trust/developer_keys.json"
)
_SCHEMA_VERSION = "plm.plugin.publisher-keys.v1"
_KEY_REF = "plm-plugin-publisher-v1"
_MAX_PRIVATE_BYTES = 8192
_MAX_MANIFEST_BYTES = 65_536


class PluginKeyCeremonyError(RuntimeError):
    """Non-sensitive failure; key material and underlying errors are not printed."""

    def __init__(self) -> None:
        super().__init__("plugin signing key ceremony unavailable")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PluginKeyCeremonyError()
        result[key] = value
    return result


def _password(passphrase: bytearray) -> bytes:
    if (
        type(passphrase) is not bytearray
        or not 24 <= len(passphrase) <= 1024
        or b"\x00" in passphrase
    ):
        raise PluginKeyCeremonyError()
    return bytes(passphrase)


def _load_manifest(path: Path) -> dict[str, object]:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > _MAX_MANIFEST_BYTES
    ):
        raise PluginKeyCeremonyError()
    try:
        value = json.loads(
            path.read_text(encoding="utf-8", errors="strict"),
            object_pairs_hook=_unique_pairs,
        )
    except Exception:
        raise PluginKeyCeremonyError() from None
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "keys"}
        or value["schema_version"] != _SCHEMA_VERSION
        or type(value["keys"]) is not list
        or len(value["keys"]) > 128
    ):
        raise PluginKeyCeremonyError()
    seen: set[str] = set()
    for item in value["keys"]:
        if (
            type(item) is not dict
            or set(item) != {"key_ref", "algorithm", "public_key", "state"}
            or type(item["key_ref"]) is not str
            or not 1 <= len(item["key_ref"].encode("utf-8")) <= 512
            or item["algorithm"] != "Ed25519"
            or item["state"] not in {"ACTIVE", "REVOKED"}
            or type(item["public_key"]) is not str
            or item["key_ref"] in seen
        ):
            raise PluginKeyCeremonyError()
        try:
            raw = base64.b64decode(item["public_key"], validate=True)
        except Exception:
            raise PluginKeyCeremonyError() from None
        if (
            len(raw) != 32
            or base64.b64encode(raw).decode("ascii") != item["public_key"]
        ):
            raise PluginKeyCeremonyError()
        seen.add(item["key_ref"])
    return value


def _validate_paths(private_path: Path, public_path: Path) -> None:
    if (
        not private_path.is_absolute()
        or not public_path.is_absolute()
        or private_path == public_path
        or private_path.parent.is_symlink()
        or public_path.parent.is_symlink()
        or not private_path.parent.is_dir()
        or not public_path.parent.is_dir()
        or private_path.is_symlink()
        or public_path.is_symlink()
    ):
        raise PluginKeyCeremonyError()


def create_pair(
    private_path: Path,
    public_path: Path,
    passphrase: bytearray,
) -> None:
    """Create the initial encrypted private key and active public trust record."""
    private_created = False
    temporary_public: Path | None = None
    try:
        password = _password(passphrase)
        _validate_paths(private_path, public_path)
        if private_path.exists() or not public_path.exists():
            raise PluginKeyCeremonyError()
        manifest = _load_manifest(public_path)
        if manifest["keys"] != []:
            # First-key ceremony only. Rotation/revocation is a separate controlled action.
            raise PluginKeyCeremonyError()

        private = Ed25519PrivateKey.generate()
        encrypted_pem = private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password),
        )
        public_raw = private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        updated_manifest = {
            "schema_version": _SCHEMA_VERSION,
            "keys": [{
                "key_ref": _KEY_REF,
                "algorithm": "Ed25519",
                "public_key": base64.b64encode(public_raw).decode("ascii"),
                "state": "ACTIVE",
            }],
        }
        manifest_bytes = (
            json.dumps(
                updated_manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        if len(encrypted_pem) > _MAX_PRIVATE_BYTES:
            raise PluginKeyCeremonyError()

        with private_path.open("xb") as stream:
            private_created = True
            stream.write(encrypted_pem)
            stream.flush()
            os.fsync(stream.fileno())

        temporary_public = public_path.with_name(
            f".{public_path.name}.{secrets.token_hex(12)}.tmp"
        )
        with temporary_public.open("xb") as stream:
            stream.write(manifest_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_public, public_path)
        temporary_public = None
        verify_pair(
            private_path,
            public_path,
            bytearray(password),
            signer_key_ref=_KEY_REF,
        )
    except Exception:
        if temporary_public is not None:
            try:
                temporary_public.unlink(missing_ok=True)
            except OSError:
                pass
        if private_created:
            try:
                private_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise PluginKeyCeremonyError() from None
    finally:
        if type(passphrase) is bytearray:
            passphrase[:] = b"\x00" * len(passphrase)


def verify_pair(
    private_path: Path,
    public_path: Path,
    passphrase: bytearray,
    *,
    signer_key_ref: str = _KEY_REF,
) -> None:
    """Verify an encrypted local or offline private-key copy against its public ref."""
    try:
        password = _password(passphrase)
        _validate_paths(private_path, public_path)
        if (
            not private_path.is_file()
            or private_path.stat().st_size < 1
            or private_path.stat().st_size > _MAX_PRIVATE_BYTES
        ):
            raise PluginKeyCeremonyError()
        manifest = _load_manifest(public_path)
        entries = [
            item for item in manifest["keys"]
            if item["key_ref"] == signer_key_ref
        ]
        if len(entries) != 1:
            raise PluginKeyCeremonyError()

        private = serialization.load_pem_private_key(
            private_path.read_bytes(),
            password=password,
        )
        if not isinstance(private, Ed25519PrivateKey):
            raise PluginKeyCeremonyError()
        public_raw = base64.b64decode(entries[0]["public_key"], validate=True)
        challenge = secrets.token_bytes(32)
        private.public_key().verify(private.sign(challenge), challenge)
        if private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        ) != public_raw:
            raise PluginKeyCeremonyError()
    except Exception:
        raise PluginKeyCeremonyError() from None
    finally:
        if type(passphrase) is bytearray:
            passphrase[:] = b"\x00" * len(passphrase)


def main() -> int:
    if (
        not sys.stdin.isatty()
        or len(sys.argv) not in (2, 3)
        or sys.argv[1] not in {"create", "verify"}
        or (sys.argv[1] == "create" and len(sys.argv) != 2)
    ):
        print(
            "Interactive terminal and create|verify [absolute-private-copy] required.",
            file=sys.stderr,
        )
        return 2
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            first = getpass.getpass("Plugin signing-key passphrase (hidden): ")
            if sys.argv[1] == "create":
                second = getpass.getpass("Confirm passphrase (hidden): ")
                if first != second:
                    raise PluginKeyCeremonyError()
        password = bytearray(first.encode("utf-8", errors="strict"))
        if sys.argv[1] == "create":
            PRIVATE_PATH.parent.mkdir(exist_ok=True)
            create_pair(PRIVATE_PATH, PUBLIC_PATH, password)
        else:
            source = Path(sys.argv[2]) if len(sys.argv) == 3 else PRIVATE_PATH
            verify_pair(source, PUBLIC_PATH, password)
        print(
            "Plugin signing key ceremony completed; keep the encrypted private key "
            "and passphrase in separate protected offline backups."
        )
        return 0
    except Exception:
        print(
            "Plugin signing key ceremony failed; no key material was printed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
