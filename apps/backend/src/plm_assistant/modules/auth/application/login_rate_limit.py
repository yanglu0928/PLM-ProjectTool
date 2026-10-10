"""Cross-process login admission; never store raw username or client address."""

from __future__ import annotations

import hashlib
import ipaddress
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

from plm_assistant.modules.auth.domain.username import UsernameValidationError, normalize_username


WINDOW = timedelta(minutes=5)
SOURCE_LIMIT = 30
ACCOUNT_LIMIT = 10


class LoginRateLimitError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LoginRateRepositoryPort(Protocol):
    def reserve(self, transaction: object, *, bucket_key: bytes, limit: int,
                window: timedelta) -> bool: ...


class LoginRateLimiter:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: LoginRateRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("login rate-limit dependencies are required")
        self._uow, self._repository = unit_of_work, repository

    def require_slot(self, *, client_ip: str, username: str) -> None:
        if (type(client_ip) is not str or len(client_ip) > 45
                or type(username) is not str or len(username) > 1024):
            raise LoginRateLimitError("AUTH_RATE_LIMITED")
        try:
            source = str(ipaddress.ip_address(client_ip))
        except ValueError:
            raise LoginRateLimitError("AUTH_RATE_LIMITED") from None
        source_key = hashlib.sha256(b"login-source\x00" + source.encode("ascii")).digest()
        try:
            normalized = normalize_username(username).normalized
        except UsernameValidationError:
            normalized = None  # Still count the source; login itself rejects malformed names.
        account_key = (hashlib.sha256(b"login-account\x00" + normalized.encode("utf-8")).digest()
                       if normalized is not None else None)
        try:
            with self._uow() as tx:
                source_allowed = self._repository.reserve(
                    tx, bucket_key=source_key, limit=SOURCE_LIMIT, window=WINDOW,
                )
                account_allowed = (self._repository.reserve(
                    tx, bucket_key=account_key, limit=ACCOUNT_LIMIT, window=WINDOW,
                ) if source_allowed and account_key is not None else source_allowed)
                tx.commit()  # Denied requests keep already consumed source capacity.
            if not source_allowed or not account_allowed:
                raise LoginRateLimitError("AUTH_RATE_LIMITED")
        except LoginRateLimitError:
            raise
        except Exception:
            raise LoginRateLimitError("SYSTEM_UNAVAILABLE") from None
