"""Portable encrypted recovery envelope for a 256-bit Secret master key."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z", re.ASCII)
_FORMAT = "PLM-SECRET-KEY-BACKUP-V1"
_N = 1 << 16
_R = 8
_P = 1
_MAX_FILE = 2048


class SecretKeyBackupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("secret key backup unavailable")


def valid_key_ref(ref: object) -> bool:
    return type(ref) is str and _REF.fullmatch(ref) is not None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(value: object, length: int) -> bytes:
    if type(value) is not str:
        raise SecretKeyBackupError()
    data = base64.b64decode(value, validate=True)
    if len(data) != length or _b64(data) != value:
        raise SecretKeyBackupError()
    return data


def _password(passphrase: str) -> bytes:
    if type(passphrase) is not str or not 16 <= len(passphrase) <= 1024:
        raise SecretKeyBackupError()
    raw = passphrase.encode("utf-8", errors="strict")
    if not 16 <= len(raw) <= 4096 or b"\x00" in raw:
        raise SecretKeyBackupError()
    return raw


def _aad(ref: str) -> bytes:
    return (_FORMAT + ":" + ref).encode("ascii")


def encrypt_backup(*, key_ref: str, master_key: bytes, passphrase: str) -> bytes:
    try:
        if not valid_key_ref(key_ref) or type(master_key) is not bytes or len(master_key) != 32:
            raise SecretKeyBackupError()
        secret = _password(passphrase)
        salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
        kek = hashlib.scrypt(secret, salt=salt, n=_N, r=_R, p=_P, dklen=32,
                             maxmem=128 * 1024 * 1024)
        ciphertext = AESGCM(kek).encrypt(nonce, master_key, _aad(key_ref))
        return json.dumps({
            "format": _FORMAT, "key_ref": key_ref, "kdf": "scrypt-65536-8-1",
            "salt": _b64(salt), "nonce": _b64(nonce), "ciphertext": _b64(ciphertext),
        }, sort_keys=True, separators=(",", ":")).encode("ascii")
    except Exception:
        raise SecretKeyBackupError() from None


def decrypt_backup(payload: bytes, *, passphrase: str) -> tuple[str, bytes]:
    try:
        if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_FILE:
            raise SecretKeyBackupError()
        value = json.loads(payload)
        if (type(value) is not dict
                or set(value) != {"format", "key_ref", "kdf", "salt", "nonce", "ciphertext"}
                or value["format"] != _FORMAT or value["kdf"] != "scrypt-65536-8-1"
                or not valid_key_ref(value["key_ref"])):
            raise SecretKeyBackupError()
        ref = value["key_ref"]
        salt = _decode(value["salt"], 16)
        nonce = _decode(value["nonce"], 12)
        ciphertext = _decode(value["ciphertext"], 48)
        kek = hashlib.scrypt(_password(passphrase), salt=salt,
                             n=_N, r=_R, p=_P, dklen=32,
                             maxmem=128 * 1024 * 1024)
        key = AESGCM(kek).decrypt(nonce, ciphertext, _aad(ref))
        if len(key) != 32:
            raise SecretKeyBackupError()
        return ref, key
    except Exception:
        raise SecretKeyBackupError() from None


def write_backup(path: Path, payload: bytes) -> None:
    """Create, never replace, an operator-chosen backup outside application data."""
    if (not isinstance(path, Path) or not path.is_absolute()
            or type(payload) is not bytes or not 1 <= len(payload) <= _MAX_FILE):
        raise SecretKeyBackupError()
    try:
        # Exclusive create also rejects an existing symlink; no auto-directory creation.
        with path.open("xb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        raise SecretKeyBackupError() from None


def read_backup(path: Path) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise SecretKeyBackupError()
    try:
        if not path.is_file() or path.stat().st_size > _MAX_FILE:
            raise SecretKeyBackupError()
        return path.read_bytes()
    except Exception:
        raise SecretKeyBackupError() from None
