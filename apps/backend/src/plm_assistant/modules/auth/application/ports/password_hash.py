"""Technology-neutral password hash contract; no raw password is persisted."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, repr=False)
class PasswordHashResult:
    password_hash: str
    algorithm_id: str
    parameter_set: Mapping[str, int]


class PasswordHasherPort(Protocol):
    def hash_password(self, password: memoryview) -> PasswordHashResult: ...
