"""Spend the normal scrypt cost for an unknown or disabled login identity."""

from __future__ import annotations

from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    N, P, PARAMETERS, R, ScryptPasswordHasher,
)


_DUMMY_HASH = f"$scrypt$1${N}${R}${P}${'00' * 16}${'00' * 32}"


class ScryptMissingIdentityVerifier:
    def __init__(self, verifier: ScryptPasswordHasher) -> None:
        if verifier is None:
            raise ValueError("password verifier is required")
        self._verifier = verifier

    def consume(self, password: bytearray) -> None:
        if type(password) is not bytearray or not 1 <= len(password) <= 1024:
            raise ValueError("invalid login proof")
        view = memoryview(password)
        try:
            if self._verifier.verify_password(
                view, password_hash=_DUMMY_HASH,
                algorithm_id="SCRYPT", parameter_set=dict(PARAMETERS),
            ) is not False:
                raise RuntimeError("invalid dummy verifier outcome")
        finally:
            view.release()
