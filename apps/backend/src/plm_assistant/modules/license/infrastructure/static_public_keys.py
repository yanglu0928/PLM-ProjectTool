"""Immutable trusted public-key registry supplied by the composition root."""

from __future__ import annotations

from collections.abc import Mapping


class StaticPublicKeyResolver:
    def __init__(self, trusted_keys: Mapping[str, bytes]) -> None:
        if not isinstance(trusted_keys, Mapping) or not trusted_keys or any(
            type(ref) is not str or not 1 <= len(ref) <= 128
            or type(key) is not bytes or len(key) != 32
            for ref, key in trusted_keys.items()
        ):
            raise ValueError("trusted public keys are required")
        self._keys = dict(trusted_keys)

    def resolve_public_key(self, public_key_ref: str) -> bytes | None:
        return self._keys.get(public_key_ref)
