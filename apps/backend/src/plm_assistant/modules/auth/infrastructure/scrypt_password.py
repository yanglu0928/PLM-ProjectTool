"""Bounded scrypt password hashing profile for Python 3.13/OpenSSL."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping

from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult


ALGORITHM_ID = "SCRYPT"
N = 1 << 17
R = 8
P = 1
DKLEN = 32
SALT_BYTES = 16
MAXMEM = 256 * 1024 * 1024
PARAMETERS = {"n": N, "r": R, "p": P, "dklen": DKLEN}
ENCODED_LEN = len(f"$scrypt$1${N}${R}${P}$") + SALT_BYTES * 2 + 1 + DKLEN * 2


class PasswordHashUnavailable(RuntimeError):
    """Fixed safe failure for missing OpenSSL or insufficient resources."""


class ScryptPasswordHasher:
    """Only the fixed V1 profile is accepted; stored parameters cannot drive work cost."""

    def hash_password(self, password: memoryview) -> PasswordHashResult:
        if not isinstance(password, memoryview) or not 1 <= len(password) <= 1024:
            raise PasswordHashUnavailable("password hashing unavailable")
        salt = secrets.token_bytes(SALT_BYTES)
        try:
            derived = hashlib.scrypt(
                password, salt=salt, n=N, r=R, p=P,
                maxmem=MAXMEM, dklen=DKLEN,
            )
        except (AttributeError, ValueError, TypeError, MemoryError):
            raise PasswordHashUnavailable("password hashing unavailable") from None
        encoded = f"$scrypt$1${N}${R}${P}${salt.hex()}${derived.hex()}"
        return PasswordHashResult(encoded, ALGORITHM_ID, dict(PARAMETERS))

    def verify_password(
        self, password: memoryview, *, password_hash: str,
        algorithm_id: str, parameter_set: Mapping[str, int],
    ) -> bool:
        if not isinstance(password, memoryview) or not 1 <= len(password) <= 1024:
            return False
        if algorithm_id != ALGORITHM_ID or type(parameter_set) is not dict or parameter_set != PARAMETERS:
            return False
        if type(password_hash) is not str or len(password_hash) != ENCODED_LEN:
            return False
        parts = password_hash.split("$")
        if len(parts) != 8 or parts[:6] != ["", "scrypt", "1", str(N), str(R), str(P)]:
            return False
        try:
            salt = bytes.fromhex(parts[6])
            expected = bytes.fromhex(parts[7])
        except ValueError:
            return False
        if len(salt) != SALT_BYTES or len(expected) != DKLEN:
            return False
        try:
            actual = hashlib.scrypt(
                password, salt=salt, n=N, r=R, p=P,
                maxmem=MAXMEM, dklen=DKLEN,
            )
        except (AttributeError, ValueError, TypeError, MemoryError):
            raise PasswordHashUnavailable("password verification unavailable") from None
        return hmac.compare_digest(actual, expected)
