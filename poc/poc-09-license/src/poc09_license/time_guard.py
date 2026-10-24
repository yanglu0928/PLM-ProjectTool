from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import LicenseError


def require_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LicenseError("LICENSE_TIME_INVALID", "License timestamps must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass
class SystemTimeGuard:
    last_seen_utc: datetime | None = None

    def validate(self, now: datetime) -> datetime:
        current = require_utc(now)
        if self.last_seen_utc is not None and current < require_utc(self.last_seen_utc):
            raise LicenseError("LICENSE_CLOCK_ROLLBACK", "System time moved backwards")
        return current

    def commit(self, now: datetime) -> None:
        self.last_seen_utc = require_utc(now)
