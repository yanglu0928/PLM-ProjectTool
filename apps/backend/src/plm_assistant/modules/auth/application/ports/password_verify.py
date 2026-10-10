"""Technology-neutral password verification boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class PasswordVerifierPort(Protocol):
    def verify_password(self, password: memoryview, *, password_hash: str,
                        algorithm_id: str, parameter_set: Mapping[str, int]) -> bool: ...
